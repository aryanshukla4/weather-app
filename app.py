# ============================================================
# app.py — The heart of the weather app (Python + Flask)
# ============================================================
# Flask is a lightweight web framework. Think of it as the
# "traffic controller" that receives requests from the browser
# and sends back the right responses.
# ============================================================

import os                          # lets us read environment variables (like API keys)
import base64
import hmac
import requests                    # lets Python make HTTP calls to external APIs
from flask import Flask, render_template, jsonify, request
from werkzeug.middleware.proxy_fix import ProxyFix
# Flask       → creates the web application
# render_template → serves HTML files from the /templates folder
# jsonify         → converts Python dicts into JSON responses for the browser
# request         → lets us read data sent by the browser (like search queries)

from dotenv import load_dotenv     # reads the .env file so secrets stay out of code
from config import Config          # our own config file (see config.py)

# ── Security Layer ─────────────────────────────────────────────
# Import everything from our dedicated security module.
# init_security wires up ALL protections (headers, logging, etc.)
# create_limiter creates the rate limiter
# validate_city / validate_coordinates check user input
from security import init_security, create_limiter, validate_city, validate_coordinates, sanitize_city

# ── Visitor Tracker ────────────────────────────────────────────
# Imports our SQLite-based tracking system.
# init_db() creates the database file and tables on first run.
from tracker import init_db, save_visitor, save_search, get_visitor_stats

# ── Load environment variables from .env ──────────────────────
load_dotenv()
# This reads .env and makes its values accessible via os.getenv()

# ── Create the Flask app ───────────────────────────────────────
app = Flask(__name__)
# __name__ tells Flask: "this file is the entry point"

app.config.from_object(Config)
# Load all settings from config.py into the Flask app

# Trust Render's proxy headers so Flask gets real client IP + HTTPS scheme.
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

# ── Initialize Security (must happen right after app creation) ──
init_security(app)
# This single call sets up:
#   - Request/response logging
#   - Security headers on every response
#   - Suspicious activity detection
#   - Custom error handlers

# ── Initialize Rate Limiter ────────────────────────────────────
limiter = create_limiter(app)
# Now we can use @limiter.limit("30/minute") on any route

# ── Initialize Database ────────────────────────────────────────
init_db()


def get_client_ip() -> str:
    """Best-effort client IP with proxy support."""
    if request.access_route:
        return request.access_route[0]
    return request.remote_addr or ""


def build_api_response(payload: dict):
    """Map service payloads to consistent HTTP responses."""
    if not payload.get("error"):
        return jsonify(payload), 200

    msg = str(payload["error"]).lower()
    if "not found" in msg:
        status = 404
    elif "invalid api key" in msg or "unauthorized" in msg:
        status = 500
    elif "timed out" in msg or "unreachable" in msg:
        status = 503
    else:
        status = 502

    return jsonify(payload), status


def _extract_basic_auth_credentials() -> tuple[str, str]:
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Basic "):
        return "", ""

    token = auth_header[6:].strip()
    try:
        decoded = base64.b64decode(token).decode("utf-8")
    except Exception:
        return "", ""

    if ":" not in decoded:
        return "", ""

    username, password = decoded.split(":", 1)
    return username, password


def require_admin_auth():
    """
    HTTP Basic auth guard for /admin/visitors.
    Env vars: ADMIN_USERNAME (optional), ADMIN_PASSWORD (required to enable auth).
    """
    admin_password = os.getenv("ADMIN_PASSWORD", "").strip()
    if not admin_password:
        return None

    admin_username = os.getenv("ADMIN_USERNAME", "admin").strip() or "admin"
    submitted_user, submitted_password = _extract_basic_auth_credentials()

    valid_user = hmac.compare_digest(submitted_user, admin_username)
    valid_pass = hmac.compare_digest(submitted_password, admin_password)
    if valid_user and valid_pass:
        return None

    response = jsonify({"error": "Unauthorized"})
    response.status_code = 401
    response.headers["WWW-Authenticate"] = 'Basic realm="Admin Dashboard"'
    return response

# ══════════════════════════════════════════════════════════════
#  ROUTE 1 — Serve the main HTML page
# ══════════════════════════════════════════════════════════════
@app.route("/")
def index():
    """
    @app.route("/") means: when someone visits http://yoursite.com/
    run this function and return its result to the browser.
    """
    return render_template("index.html")
    # render_template looks in the /templates folder for index.html
    # and sends it back to the browser as a webpage


# ══════════════════════════════════════════════════════════════
#  ROUTE 2 — Fetch current weather by city name
# ══════════════════════════════════════════════════════════════
@app.route("/api/weather")
@limiter.limit("30/minute")
# This route gets a STRICTER limit than the default.
# 30 calls/minute per IP is plenty for real users.
# Stops scrapers and bots from hammering the API.
def get_weather():
    """
    This is an API endpoint — the browser calls this behind the scenes
    (via JavaScript fetch) and gets back JSON weather data.

    Example call from browser:
      GET /api/weather?city=Mumbai
    """

    city = request.args.get("city", "").strip()

    # ── SECURITY: Validate city name before using it ─────────
    is_valid, error_message = validate_city(city)
    if not is_valid:
        app.logger.info(f"INVALID_CITY | value='{city[:50]}' | reason={error_message}")
        return jsonify({"error": error_message}), 400

    city = sanitize_city(city)
    # sanitize_city cleans up extra spaces and limits length

    weather_data = fetch_weather_by_city(city)
    if not weather_data.get("error"):
        log_search(city)   # record this search in the database
    return build_api_response(weather_data)


# ══════════════════════════════════════════════════════════════
#  ROUTE 3 — Fetch weather by GPS coordinates (lat/lon)
# ══════════════════════════════════════════════════════════════
@app.route("/api/weather/coords")
@limiter.limit("20/minute")
# Coordinates endpoint gets 20/min — slightly lower because
# geolocation is only used once on page load.
def get_weather_by_coords():
    """
    The browser can ask: "what's the weather at my exact location?"
    It sends latitude and longitude, and we return the weather.

    Example: GET /api/weather/coords?lat=19.07&lon=72.87
    """

    lat_str = request.args.get("lat", "")
    lon_str = request.args.get("lon", "")

    # ── SECURITY: Validate coordinates ───────────────────────
    # validate_coordinates checks: are they numbers? in valid range?
    # are they NaN or Infinity? This prevents crashes and injection.
    is_valid, error_message, lat, lon = validate_coordinates(lat_str, lon_str)
    if not is_valid:
        app.logger.info(f"INVALID_COORDS | lat='{lat_str}' lon='{lon_str}' | reason={error_message}")
        return jsonify({"error": error_message}), 400

    weather_data = fetch_weather_by_coords(lat, lon)
    return build_api_response(weather_data)


# ══════════════════════════════════════════════════════════════
#  ROUTE 4 — Fetch 5-day forecast by city name
# ══════════════════════════════════════════════════════════════
@app.route("/api/forecast")
@limiter.limit("30/minute")
def get_forecast():
    """
    Returns a 5-day weather forecast (3-hour intervals).
    The frontend groups these into daily summaries.
    """

    city = request.args.get("city", "").strip()

    # ── SECURITY: Validate & sanitize ────────────────────────
    is_valid, error_message = validate_city(city)
    if not is_valid:
        return jsonify({"error": error_message}), 400

    city = sanitize_city(city)

    forecast_data = fetch_forecast(city)
    return build_api_response(forecast_data)


# ══════════════════════════════════════════════════════════════
#  HELPER FUNCTIONS — The actual API calls to OpenWeatherMap
# ══════════════════════════════════════════════════════════════

def get_openweather_api_key() -> str:
    return app.config.get("OPENWEATHER_API_KEY", "").strip()


def fetch_weather_by_city(city: str) -> dict:
    """
    Calls the OpenWeatherMap API with a city name.
    Returns a clean dict of weather info.
    Type hint 'city: str' and '-> dict' are just documentation — 
    they tell other developers what goes in and what comes out.
    """

    api_key = get_openweather_api_key()
    if not api_key:
        return {"error": "Server is missing OPENWEATHER_API_KEY."}
    # Read API key from our config (which reads from .env)

    url = "https://api.openweathermap.org/data/2.5/weather"
    # This is OpenWeatherMap's "current weather" endpoint

    params = {
        "q":     city,          # city name
        "appid": api_key,       # our API key for authentication
        "units": "metric",      # use Celsius (use "imperial" for Fahrenheit)
        "lang":  "en",          # English descriptions
    }

    try:
        response = requests.get(url, params=params, timeout=app.config.get("REQUEST_TIMEOUT", 10))
        # timeout=10 → if the API doesn't respond in 10 seconds, stop waiting

        if response.status_code == 404:
            return {"error": f"City '{city}' not found. Check the spelling."}

        if response.status_code == 401:
            return {"error": "Invalid API key. Check your .env file."}

        response.raise_for_status()
        # raise_for_status() throws an error for any 4xx or 5xx HTTP status

        data = response.json()
        # .json() parses the response body from text into a Python dict

        return parse_weather(data)
        # We clean up the raw API data before sending it to the browser

    except requests.exceptions.ConnectionError:
        return {"error": "No internet connection or API unreachable."}
    except requests.exceptions.Timeout:
        return {"error": "Request timed out. Try again."}
    except Exception as e:
        return {"error": f"Unexpected error: {str(e)}"}


def fetch_weather_by_coords(lat: float, lon: float) -> dict:
    """
    Same as above but using GPS coordinates instead of a city name.
    Useful for the "Use My Location" browser feature.
    """

    api_key = get_openweather_api_key()
    if not api_key:
        return {"error": "Server is missing OPENWEATHER_API_KEY."}
    url = "https://api.openweathermap.org/data/2.5/weather"

    params = {
        "lat":   lat,
        "lon":   lon,
        "appid": api_key,
        "units": "metric",
        "lang":  "en",
    }

    try:
        response = requests.get(url, params=params, timeout=app.config.get("REQUEST_TIMEOUT", 10))
        if response.status_code == 401:
            return {"error": "Invalid API key. Check your environment variables."}
        response.raise_for_status()
        return parse_weather(response.json())
    except requests.exceptions.ConnectionError:
        return {"error": "No internet connection or API unreachable."}
    except requests.exceptions.Timeout:
        return {"error": "Request timed out. Try again."}
    except Exception as e:
        return {"error": f"Unexpected error: {str(e)}"}


def fetch_forecast(city: str) -> dict:
    """
    Calls OpenWeatherMap's 5-day forecast API.
    Returns data every 3 hours for 5 days = 40 data points.
    We'll process them into daily summaries on the frontend.
    """

    api_key = get_openweather_api_key()
    if not api_key:
        return {"error": "Server is missing OPENWEATHER_API_KEY."}
    url = "https://api.openweathermap.org/data/2.5/forecast"

    params = {
        "q":     city,
        "appid": api_key,
        "units": "metric",
        "lang":  "en",
    }

    try:
        response = requests.get(url, params=params, timeout=app.config.get("REQUEST_TIMEOUT", 10))

        if response.status_code == 404:
            return {"error": f"City '{city}' not found."}

        response.raise_for_status()
        data = response.json()

        # Process the raw 3-hourly list into daily summaries
        return parse_forecast(data)

    except requests.exceptions.ConnectionError:
        return {"error": "No internet connection or API unreachable."}
    except requests.exceptions.Timeout:
        return {"error": "Request timed out. Try again."}
    except Exception as e:
        return {"error": f"Unexpected error: {str(e)}"}


# ══════════════════════════════════════════════════════════════
#  DATA PARSERS — Clean up raw API data
# ══════════════════════════════════════════════════════════════

def parse_weather(data: dict) -> dict:
    """
    The raw OpenWeatherMap response has lots of nested fields.
    This function extracts only what we need and puts it in a
    flat, easy-to-use dict.
    """

    return {
        "city":        data["name"],                          # e.g. "Mumbai"
        "country":     data["sys"]["country"],                # e.g. "IN"
        "temp":        round(data["main"]["temp"]),           # e.g. 31
        "feels_like":  round(data["main"]["feels_like"]),     # "feels like" temp
        "temp_min":    round(data["main"]["temp_min"]),
        "temp_max":    round(data["main"]["temp_max"]),
        "humidity":    data["main"]["humidity"],              # percentage 0-100
        "pressure":    data["main"]["pressure"],              # hPa
        "description": data["weather"][0]["description"],     # e.g. "light rain"
        "icon":        data["weather"][0]["icon"],            # icon code e.g. "10d"
        "wind_speed":  data["wind"]["speed"],                 # m/s
        "wind_deg":    data["wind"].get("deg", 0),            # wind direction in degrees
        "visibility":  data.get("visibility", 0) // 1000,    # convert meters → km
        "sunrise":     data["sys"]["sunrise"],                # Unix timestamp
        "sunset":      data["sys"]["sunset"],                 # Unix timestamp
        "timezone":    data["timezone"],                      # seconds offset from UTC
        "lat":         data["coord"]["lat"],
        "lon":         data["coord"]["lon"],
    }


def parse_forecast(data: dict) -> dict:
    """
    Processes the 3-hourly forecast list into per-day summaries.
    Each day gets: min temp, max temp, average humidity, description, icon.
    """

    from collections import defaultdict
    # defaultdict creates a dict that automatically creates empty lists
    # for new keys — saves us from checking "if key exists" each time

    days = defaultdict(list)
    # Structure: { "2025-07-15": [list of 3-hour entries for that day], ... }

    for item in data["list"]:
        # item["dt_txt"] looks like "2025-07-15 12:00:00"
        date_str = item["dt_txt"].split(" ")[0]  # get just "2025-07-15"
        days[date_str].append(item)

    result = []
    for date, entries in list(days.items())[:5]:  # max 5 days
        temps     = [e["main"]["temp"] for e in entries]
        # List comprehension: loops over entries and pulls out each temp

        humidities = [e["main"]["humidity"] for e in entries]

        # Use the midday entry for description/icon if available
        midday = next((e for e in entries if "12:00:00" in e["dt_txt"]), entries[0])
        # next() finds the first entry matching the condition, or falls back to entries[0]

        result.append({
            "date":        date,
            "temp_min":    round(min(temps)),   # coldest of the day
            "temp_max":    round(max(temps)),   # hottest of the day
            "humidity":    round(sum(humidities) / len(humidities)),  # average
            "description": midday["weather"][0]["description"],
            "icon":        midday["weather"][0]["icon"],
        })

    return {"forecast": result, "city": data["city"]["name"]}



# ══════════════════════════════════════════════════════════════
#  ROUTE 5 — Receive visitor tracking data from browser
# ══════════════════════════════════════════════════════════════
@app.route("/api/track", methods=["POST"])
@limiter.limit("10/minute")
# POST method because the browser is SENDING data to us.
# 10/min limit — one visitor shouldn't fire this more than once anyway.
def track():
    """
    Receives visitor data sent silently by app.js on page load.
    Saves it to the SQLite database via tracker.py.
    Returns a simple OK — the browser doesn't use the response.
    """
    try:
        data = request.get_json(silent=True) or {}
        # silent=True means: if the body isn't valid JSON, return None
        # instead of throwing an error. We handle None with "or {}"

        ip = get_client_ip()

        visitor_id = save_visitor(data, ip)
        return jsonify({"ok": True, "id": visitor_id})

    except Exception as e:
        app.logger.error(f"Track error: {e}")
        return jsonify({"ok": False}), 200
        # Return 200 even on error so the browser doesn't retry or show warnings.
        # Tracking failure should NEVER affect the user's experience.


# ══════════════════════════════════════════════════════════════
#  ROUTE 6 — Log a city search (called from weather route)
# ══════════════════════════════════════════════════════════════
def log_search(city: str):
    """
    Helper called inside get_weather() to record every city searched.
    Not a route itself — just a function called by the weather route.
    """
    try:
        ip = get_client_ip()
        save_search(ip=ip, city=city)
    except Exception:
        pass  # Never break weather search because of tracking failure


# ══════════════════════════════════════════════════════════════
#  ROUTE 7 — Admin dashboard to view all visitor data
# ══════════════════════════════════════════════════════════════
@app.route("/admin/visitors")
def admin_visitors():
    """
    Renders the admin analytics dashboard.

    All the HTML lives in templates/admin.html — not here.
    render_template() loads that file and fills in the {{ variables }}
    using the stats dict we pass to it.

    Access locally:  http://localhost:5000/admin/visitors
    In production: use HTTP Basic auth with ADMIN_USERNAME/ADMIN_PASSWORD.
    """

    # ── Password protection ───────────────────────────────────
    auth_error = require_admin_auth()
    if auth_error:
        return auth_error

    # Fetch all analytics data from tracker.py
    stats = get_visitor_stats()

    # render_template() finds templates/admin.html and passes stats to it.
    # Inside admin.html, {{ stats.total }}, {{ stats.countries }} etc.
    # get replaced with the real values from this dict.
    return render_template("admin.html", stats=stats)


# ══════════════════════════════════════════════════════════════
#  START THE APP
# ══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    # This block only runs when you do: python app.py
    # It does NOT run in production (Gunicorn handles that instead)

    port = int(os.getenv("PORT", 5000))
    # On Render, PORT is set automatically. Locally it defaults to 5000.

    debug = os.getenv("FLASK_ENV", "production") == "development"
    # Debug mode reloads the server automatically when you change code.
    # NEVER use debug=True in production — it exposes internals.

    app.run(host="0.0.0.0", port=port, debug=debug)
    # host="0.0.0.0" means "accept connections from any network interface"
    # This is required when running inside Docker or on a server.

