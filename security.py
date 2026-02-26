# ============================================================
# security.py — Complete Security Layer for the Weather App
# ============================================================
#
# This module handles ALL security concerns in one place:
#
#   1. Rate Limiting      → stops bots & abusers from hammering your API
#   2. Security Headers   → browser-level protections (XSS, clickjacking, etc.)
#   3. Input Validation   → rejects malicious or malformed input before it
#                           ever reaches your business logic
#   4. Request Logging    → records every request for auditing & debugging
#   5. Suspicious Activity Detection → auto-blocks IPs doing bad things
#   6. Error Hardening    → ensures errors never leak internal details
#
# WHY A SEPARATE FILE?
#   Keeping security in its own module means:
#   - app.py stays clean and readable
#   - Security can be reviewed, tested, updated independently
#   - Easy to add new security rules without touching routes
# ============================================================

import re                   # regular expressions — for pattern matching on input
import time                 # for timestamps in logs
import logging              # Python's built-in logging system
import ipaddress            # for validating and parsing IP addresses
from datetime import datetime, timezone
from functools import wraps # for writing decorators (explained below)
from collections import defaultdict, deque

from flask import request, jsonify, g
# g is Flask's "request context global" — a temporary scratchpad that lives
# for exactly one request. Perfect for storing per-request data like timing.

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
# flask_limiter → adds rate limiting to Flask routes
# get_remote_address → extracts the caller's IP address from the request


# ══════════════════════════════════════════════════════════════
#  LOGGING SETUP
#  Python's logging module writes messages to files/console.
#  Much better than print() for production — supports log levels,
#  timestamps, and can write to multiple destinations at once.
# ══════════════════════════════════════════════════════════════

def setup_logging(app):
    """
    Configures two log streams:
      - Console: colored output for development
      - File: persistent log file for production auditing

    Log levels (in order of severity):
      DEBUG    → very detailed, dev only
      INFO     → normal operations (requests, searches)
      WARNING  → something unusual but not broken
      ERROR    → something failed
      CRITICAL → app-breaking failure
    """

    # Create a formatter that includes timestamp, level, and message
    formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)-8s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    # %(asctime)s    → "2025-07-15 14:32:01"
    # %(levelname)-8s → "INFO    " (padded to 8 chars for alignment)
    # %(message)s    → the actual log message

    # ── Console Handler: prints logs to terminal ────────────
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)

    # ── File Handler: writes logs to a file ─────────────────
    file_handler = logging.FileHandler("weather_app.log")
    # All logs saved to weather_app.log in the project root
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.WARNING)
    # Only WARNING and above go to file — keeps log file from filling up

    # ── Attach handlers to the app's logger ─────────────────
    app.logger.addHandler(console_handler)
    app.logger.addHandler(file_handler)
    app.logger.setLevel(logging.INFO)
    # The logger itself is set to INFO — handlers can be more restrictive

    return app.logger


# ══════════════════════════════════════════════════════════════
#  RATE LIMITER
#  Limits how many requests a single IP can make per time window.
#  This prevents:
#    - Bots scraping your API thousands of times per second
#    - Someone trying to rack up your OpenWeatherMap API bill
#    - Accidental infinite loops in someone's code hitting your server
# ══════════════════════════════════════════════════════════════

def create_limiter(app):
    """
    Creates and configures the Flask-Limiter instance.

    Limits are expressed as "count/period":
      "30/minute"  → 30 requests per minute
      "200/hour"   → 200 requests per hour
      "5/second"   → 5 requests per second (for burst protection)

    Storage: We use memory storage here (simple, no extra setup).
    For production with multiple server processes, switch to Redis:
      storage_uri="redis://localhost:6379"
    """

    limiter = Limiter(
        app=app,
        key_func=get_remote_address,
        # key_func tells the limiter HOW to identify each "user"
        # get_remote_address uses the caller's IP address as the key
        # So each IP gets its own separate counter.

        default_limits=["200/day", "50/hour"],
        # These apply to EVERY route automatically.
        # 200 requests per day and 50 per hour per IP.

        storage_uri="memory://",
        # Stores counters in RAM. Fast, but resets on restart.
        # Production tip: use "redis://localhost:6379" for persistence.

        headers_enabled=True,
        # Adds rate limit info to HTTP response headers so clients can see:
        #   X-RateLimit-Limit: 30
        #   X-RateLimit-Remaining: 27
        #   X-RateLimit-Reset: 1720000000
        # This lets good clients back off before hitting the limit.

        on_breach=rate_limit_breached,
        # Custom function called when a limit is exceeded
    )

    return limiter


def rate_limit_breached(request_limit):
    """
    Called automatically by flask-limiter when a rate limit is hit.
    Returns a clean JSON error instead of flask-limiter's default HTML.
    Also logs the event so you can monitor abuse.
    """
    ip = get_remote_address()
    logging.warning(f"RATE_LIMIT_BREACHED | IP={ip} | Path={request.path} | Limit={request_limit}")

    return jsonify({
        "error": "Too many requests. Please slow down.",
        "retry_after": "60 seconds"
    }), 429
    # HTTP 429 = "Too Many Requests" — the correct status code for rate limiting


# ══════════════════════════════════════════════════════════════
#  SECURITY HEADERS
#  HTTP response headers that instruct the browser to apply
#  various security policies. These are free protections that
#  cost nothing in performance but prevent entire attack classes.
# ══════════════════════════════════════════════════════════════

def apply_security_headers(response):
    """
    Adds security headers to EVERY response the server sends.
    This is attached as an @app.after_request hook in app.py,
    so it runs automatically after every route handler.

    Think of these headers as instructions you give to the browser:
    "Here are the rules you must follow when running this page."
    """

    # ── Content-Security-Policy (CSP) ────────────────────────
    # The most powerful header. Tells the browser exactly which
    # sources are allowed to load scripts, styles, images, etc.
    # If an attacker injects a <script src="evil.com/hack.js">,
    # the browser will BLOCK it because evil.com isn't in our list.
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        # default-src 'self' → by default, only load from our own domain

        "script-src 'self'; "
        # scripts only from our own /static/js/ folder

        "style-src 'self' https://fonts.googleapis.com; "
        # styles from us + Google Fonts CSS

        "font-src 'self' https://fonts.gstatic.com; "
        # font files from us + Google's font CDN

        "img-src 'self' https://openweathermap.org data:; "
        # images from us + OpenWeatherMap (weather icons) + data: URIs

        "connect-src 'self'; "
        # fetch()/XHR only allowed to call our own domain

        "frame-ancestors 'none'; "
        # nobody can embed our site in an <iframe> (prevents clickjacking)

        "base-uri 'self'; "
        # <base> tag can only point to our own domain

        "form-action 'self';"
        # forms can only submit to our own domain
    )

    # ── X-Content-Type-Options ────────────────────────────────
    # Prevents "MIME sniffing" — where browsers guess file types.
    # Without this, a browser might run a text file as JavaScript
    # if an attacker tricks it into thinking it's a script.
    response.headers["X-Content-Type-Options"] = "nosniff"

    # ── X-Frame-Options ───────────────────────────────────────
    # Older browsers that don't support CSP frame-ancestors.
    # Prevents our site from being embedded in iframes.
    # Clickjacking attack: evil site puts our site in a transparent
    # iframe and tricks users into clicking our buttons unknowingly.
    response.headers["X-Frame-Options"] = "DENY"

    # ── Referrer-Policy ───────────────────────────────────────
    # Controls how much info is sent in the Referer header when
    # users click links going off our site.
    # "strict-origin-when-cross-origin" → send only the domain
    # (not the full URL) when navigating to other sites.
    # Prevents leaking sensitive URL parameters to third parties.
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

    # ── Permissions-Policy ────────────────────────────────────
    # Restricts which browser APIs this page can use.
    # We're a weather app — we need geolocation but nothing else.
    # This prevents third-party scripts from secretly using camera,
    # microphone, or payment APIs even if they were somehow injected.
    response.headers["Permissions-Policy"] = (
        "geolocation=self, "         # only our page can request GPS
        "camera=(), "                # nobody can access camera
        "microphone=(), "            # nobody can access microphone
        "payment=(), "               # no payment APIs
        "usb=(), "                   # no USB access
        "magnetometer=(), "
        "gyroscope=()"
    )

    # ── Cache-Control for API responses ───────────────────────
    # Tell browsers NOT to cache our API responses.
    # We want fresh weather data every time.
    if request.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        # Pragma: no-cache is for old HTTP/1.0 clients

    # ── Remove server fingerprinting ──────────────────────────
    # By default, Flask sends "Server: Werkzeug/3.x" in responses.
    # This tells attackers exactly what software to look up exploits for.
    # We replace it with a generic value.
    response.headers["Server"] = "Nimbus"
    # Remove Flask's default X-Powered-By if present
    response.headers.pop("X-Powered-By", None)

    return response


def apply_hsts(response):
    """
    HSTS = HTTP Strict Transport Security
    Tells browsers: "Always use HTTPS for this domain. Never HTTP."
    
    IMPORTANT: Only add this header if you're on HTTPS.
    If you add it on HTTP, you'll lock users out permanently!
    We check for HTTPS before adding it.
    """
    if request.is_secure:
        # is_secure = True when the connection is HTTPS
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains"
            # max-age=31536000 → enforce HTTPS for 1 year (in seconds)
            # includeSubDomains → applies to all subdomains too
        )
    return response


# ══════════════════════════════════════════════════════════════
#  INPUT VALIDATION
#  Never trust data coming from users. Validate and sanitize
#  ALL input before using it in your code.
#
#  Threats we're defending against:
#    - SQL Injection (not applicable here, but good practice)
#    - XSS via reflected input
#    - Path traversal attacks (../../etc/passwd)
#    - Extremely long inputs crashing the server
#    - Latitude/longitude values that are clearly impossible
# ══════════════════════════════════════════════════════════════

# Regex pattern for valid city names.
# Allows: letters (including accents for e.g. São Paulo, München),
#         spaces, hyphens, apostrophes, commas (for "London, UK")
# Blocks: HTML tags, script injection, path traversal, SQL syntax
VALID_CITY_PATTERN = re.compile(
    r"^[a-zA-ZÀ-ÿ\u0900-\u097F\s\-\',\.]{1,100}$",
    re.UNICODE
    # À-ÿ covers accented Latin (é, ñ, ü, etc.)
    # \u0900-\u097F covers Devanagari script (Hindi city names)
    # {1,100} = between 1 and 100 characters
)

def validate_city(city: str) -> tuple[bool, str]:
    """
    Validates a city name string.
    Returns: (is_valid: bool, error_message: str)
    
    The tuple return lets callers check both the result AND the
    specific reason for rejection in one call.
    """

    if not city:
        return False, "City name cannot be empty."

    city = city.strip()

    if len(city) < 2:
        return False, "City name is too short."

    if len(city) > 100:
        return False, "City name is too long. Maximum 100 characters."

    # Block obvious script injection attempts
    dangerous_patterns = [
        "<script", "</script>", "javascript:", "onerror=",
        "onload=", "../", "..\\", "DROP TABLE", "SELECT *",
        "%3Cscript", "eval(", "document.cookie"
    ]
    city_lower = city.lower()
    for pattern in dangerous_patterns:
        if pattern.lower() in city_lower:
            return False, "Invalid characters in city name."

    # Check against allowed character pattern
    if not VALID_CITY_PATTERN.match(city):
        return False, "City name contains invalid characters."

    return True, ""
    # Empty string for error when valid


def validate_coordinates(lat_str: str, lon_str: str) -> tuple[bool, str, float, float]:
    """
    Validates latitude and longitude strings.
    Returns: (is_valid, error_message, lat_float, lon_float)
    
    Valid ranges:
      Latitude:  -90  to  +90  (south pole to north pole)
      Longitude: -180 to +180  (west to east around the globe)
    """

    # Check they're not empty
    if not lat_str or not lon_str:
        return False, "Latitude and longitude are required.", 0.0, 0.0

    try:
        lat = float(lat_str)
        lon = float(lon_str)
        # float() will raise ValueError if the string isn't a number
        # This blocks inputs like "hello", "99999999999", etc.
    except (ValueError, TypeError):
        return False, "Coordinates must be valid numbers.", 0.0, 0.0

    # Check realistic geographic bounds
    if not (-90 <= lat <= 90):
        return False, f"Latitude must be between -90 and 90. Got: {lat}", 0.0, 0.0

    if not (-180 <= lon <= 180):
        return False, f"Longitude must be between -180 and 180. Got: {lon}", 0.0, 0.0

    # Check for NaN or Infinity (float("nan"), float("inf"))
    import math
    if math.isnan(lat) or math.isnan(lon) or math.isinf(lat) or math.isinf(lon):
        return False, "Coordinates cannot be NaN or Infinity.", 0.0, 0.0

    return True, "", lat, lon


def sanitize_city(city: str) -> str:
    """
    Cleans a city name after it passes validation.
    Strips excess whitespace and normalizes it slightly.
    """
    # Strip whitespace from both ends
    city = city.strip()

    # Collapse multiple spaces into one (e.g. "New  York" → "New York")
    city = re.sub(r"\s+", " ", city)

    # Limit to 100 characters (extra safety)
    city = city[:100]

    return city


# ══════════════════════════════════════════════════════════════
#  REQUEST LOGGING MIDDLEWARE
#  Logs every incoming request with timing information.
#  Useful for:
#    - Debugging production issues
#    - Monitoring which cities are searched most
#    - Spotting abuse patterns
# ══════════════════════════════════════════════════════════════

def log_request_start():
    """
    Runs BEFORE every request (attached via @app.before_request).
    Records the start time in Flask's 'g' object.
    'g' is a temporary per-request scratchpad — it's empty at the
    start of each request and discarded when the response is sent.
    """
    g.start_time = time.monotonic()
    # time.monotonic() is better than time.time() for measuring durations
    # because it can't go backwards (e.g. during daylight saving time changes)


def log_request_end(response):
    """
    Runs AFTER every request (attached via @app.after_request).
    Calculates how long the request took and logs it.
    """

    duration_ms = round((time.monotonic() - g.start_time) * 1000, 2)
    # Multiply by 1000 to convert seconds → milliseconds

    ip = get_remote_address()

    # Only log API calls (skip static files like CSS/JS — too noisy)
    if request.path.startswith("/api/") or request.path == "/":
        log_level = logging.WARNING if response.status_code >= 400 else logging.INFO
        # Use WARNING for 4xx/5xx errors, INFO for successful requests

        logging.log(
            log_level,
            f"REQUEST | {request.method} {request.path} | "
            f"Status={response.status_code} | "
            f"IP={ip} | "
            f"Duration={duration_ms}ms | "
            f"UA={request.headers.get('User-Agent', 'unknown')[:60]}"
            # UA = User Agent (browser/bot identifier)
            # [:60] limits to 60 chars to keep logs readable
        )

    return response


# ══════════════════════════════════════════════════════════════
#  SUSPICIOUS ACTIVITY DETECTOR
#  Watches for patterns that suggest malicious behavior and
#  temporarily blocks offending IPs.
#
#  Detected behaviors:
#    - Rapid-fire requests (more than 10 per second)
#    - Port scanning (requesting paths that don't exist repeatedly)
#    - Known bad user agents (automated scanning tools)
# ══════════════════════════════════════════════════════════════

# In-memory store of IPs and their recent request timestamps
# deque = double-ended queue with a max length (auto-drops oldest entries)
_request_history = defaultdict(lambda: deque(maxlen=50))
# maxlen=50 means each IP only stores its last 50 request timestamps

# Temporarily blocked IPs → {ip: unblock_timestamp}
_blocked_ips = {}

# Known malicious/scanner user agents (partial matches)
BANNED_USER_AGENTS = [
    "sqlmap",         # SQL injection scanner
    "nikto",          # web vulnerability scanner
    "nmap",           # network port scanner
    "masscan",        # mass port scanner
    "zgrab",          # web fingerprinting tool
    "python-requests/2.1",  # very old requests version, often bots
    "dirbuster",      # directory brute-force tool
    "hydra",          # password brute-force tool
]

# Paths that legitimate users never request (signs of scanning/hacking)
SUSPICIOUS_PATHS = [
    "/wp-admin",       # WordPress admin (we're not WordPress)
    "/wp-login.php",
    "/.env",           # trying to steal our secrets file
    "/admin",
    "/phpmyadmin",     # PHP database admin tool
    "/.git/config",    # trying to steal our git config
    "/etc/passwd",     # Linux password file
    "/shell",
    "/cmd",
    "/.htaccess",
]

BURST_LIMIT = 10       # max requests per second before blocking
BLOCK_DURATION = 300   # block duration in seconds (5 minutes)


def check_suspicious_activity():
    """
    Runs before every request.
    Checks if the current IP is behaving suspiciously.
    If so, returns a 403 Forbidden response to block them.
    """

    ip = get_remote_address()
    now = time.monotonic()

    # ── Check if IP is currently blocked ────────────────────
    if ip in _blocked_ips:
        unblock_time = _blocked_ips[ip]
        if now < unblock_time:
            remaining = round(unblock_time - now)
            logging.warning(f"BLOCKED_IP_ATTEMPT | IP={ip} | Path={request.path}")
            return jsonify({
                "error": "Your IP has been temporarily blocked due to suspicious activity.",
                "retry_after": f"{remaining} seconds"
            }), 403
        else:
            # Block expired — remove from blocked list
            del _blocked_ips[ip]

    # ── Check User Agent ─────────────────────────────────────
    user_agent = request.headers.get("User-Agent", "").lower()
    for banned_ua in BANNED_USER_AGENTS:
        if banned_ua in user_agent:
            logging.warning(f"BANNED_UA | IP={ip} | UA={user_agent[:80]}")
            _block_ip(ip, "Banned user agent")
            return jsonify({"error": "Access denied."}), 403

    # ── Check for suspicious path requests ───────────────────
    path_lower = request.path.lower()
    for suspicious_path in SUSPICIOUS_PATHS:
        if suspicious_path in path_lower:
            logging.warning(f"SUSPICIOUS_PATH | IP={ip} | Path={request.path}")
            _block_ip(ip, f"Accessed suspicious path: {request.path}")
            return jsonify({"error": "Not found."}), 404
            # Return 404 not 403 — don't confirm the path exists

    # ── Check request burst rate ──────────────────────────────
    history = _request_history[ip]
    history.append(now)

    # Count how many requests in the last 1 second
    one_second_ago = now - 1.0
    recent_count = sum(1 for t in history if t > one_second_ago)

    if recent_count > BURST_LIMIT:
        logging.warning(
            f"BURST_DETECTED | IP={ip} | "
            f"Requests in last second={recent_count} | "
            f"Path={request.path}"
        )
        _block_ip(ip, f"Burst rate {recent_count} req/sec")
        return jsonify({
            "error": "Too many rapid requests. You have been temporarily blocked.",
            "retry_after": f"{BLOCK_DURATION} seconds"
        }), 429

    return None
    # Returning None means "no problem found, continue normally"


def _block_ip(ip: str, reason: str):
    """
    Adds an IP to the temporary blocklist.
    Private function (leading underscore = not for external use).
    """
    unblock_at = time.monotonic() + BLOCK_DURATION
    _blocked_ips[ip] = unblock_at
    logging.warning(
        f"IP_BLOCKED | IP={ip} | Reason={reason} | "
        f"Duration={BLOCK_DURATION}s | "
        f"Unblocks at={datetime.now(timezone.utc).isoformat()}"
    )


# ══════════════════════════════════════════════════════════════
#  ERROR HARDENING
#  Flask's default error pages show stack traces in development.
#  In production, we NEVER want to show internal details to users.
#  These handlers return clean JSON errors instead.
# ══════════════════════════════════════════════════════════════

def register_error_handlers(app):
    """
    Registers custom error handlers for common HTTP error codes.
    Call this once in app.py after creating the Flask app.
    """

    @app.errorhandler(400)
    def bad_request(e):
        # 400 = Bad Request (malformed input)
        return jsonify({"error": "Bad request. Please check your input."}), 400

    @app.errorhandler(404)
    def not_found(e):
        # 404 = Not Found
        # We return JSON instead of Flask's default HTML 404 page.
        # This is consistent with our API's JSON response format.
        return jsonify({"error": "The requested resource was not found."}), 404

    @app.errorhandler(405)
    def method_not_allowed(e):
        # 405 = Method Not Allowed (e.g. someone sends POST to a GET endpoint)
        return jsonify({"error": "HTTP method not allowed for this endpoint."}), 405

    @app.errorhandler(429)
    def too_many_requests(e):
        # 429 = Too Many Requests (rate limit hit)
        return jsonify({
            "error": "Too many requests. Please wait before trying again.",
            "retry_after": "60 seconds"
        }), 429

    @app.errorhandler(500)
    def internal_error(e):
        # 500 = Internal Server Error
        # Log the full error internally (for our debugging)
        app.logger.error(f"INTERNAL_ERROR | {str(e)} | Path={request.path}")
        # But only return a generic message to the user
        # (never expose stack traces, variable names, file paths)
        return jsonify({
            "error": "An internal error occurred. Please try again later."
        }), 500

    @app.errorhandler(Exception)
    def unhandled_exception(e):
        # Catch-all for any exception we didn't explicitly handle
        app.logger.critical(
            f"UNHANDLED_EXCEPTION | {type(e).__name__}: {str(e)} | "
            f"Path={request.path} | IP={get_remote_address()}"
        )
        return jsonify({
            "error": "Something went wrong. Please try again later."
        }), 500


# ══════════════════════════════════════════════════════════════
#  REQUIRE HTTPS REDIRECT (production only)
# ══════════════════════════════════════════════════════════════

def enforce_https():
    """
    Redirects HTTP requests to HTTPS in production.
    Only runs if FORCE_HTTPS=true is set in your environment.
    Render provides HTTPS automatically, so this mainly serves
    as an extra safety net.
    """
    import os
    from flask import redirect

    if os.getenv("FORCE_HTTPS", "false").lower() == "true":
        if not request.is_secure and request.headers.get("X-Forwarded-Proto", "http") != "https":
            # X-Forwarded-Proto is set by reverse proxies (like Render's load balancer)
            # to indicate the original protocol the user used.
            url = request.url.replace("http://", "https://", 1)
            return redirect(url, code=301)
            # 301 = Permanent Redirect — browsers remember this forever
    return None


# ══════════════════════════════════════════════════════════════
#  MAIN SETUP FUNCTION
#  Call this once from app.py to wire everything together.
# ══════════════════════════════════════════════════════════════

def init_security(app):
    """
    One-call setup for all security features.
    Import this in app.py and call it right after creating the Flask app.

    Usage in app.py:
        from security import init_security, create_limiter
        init_security(app)
        limiter = create_limiter(app)
    """

    # Set up logging
    setup_logging(app)

    # Register error handlers
    register_error_handlers(app)

    # Attach middleware hooks
    app.before_request(enforce_https)
    app.before_request(check_suspicious_activity)
    app.before_request(log_request_start)

    app.after_request(apply_security_headers)
    app.after_request(apply_hsts)
    app.after_request(log_request_end)

    app.logger.info("Security layer initialized ✓")

    return app