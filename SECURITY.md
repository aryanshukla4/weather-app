# 🔒 Security Guide — Nimbus Weather App

Every protection explained in plain English.

---

## What's Protected and Why

### 1. Rate Limiting — `flask-limiter`

**What it does:** Limits how many requests one IP address can make per time window.

**Limits applied:**
| Endpoint | Limit | Why |
|----------|-------|-----|
| All routes (default) | 200/day, 50/hour | Global safety net |
| `/api/weather` | 30/minute | Weather calls — generous for humans |
| `/api/weather/coords` | 20/minute | GPS calls — once per page load |
| `/api/forecast` | 30/minute | Forecast calls — same as weather |

**What it blocks:**
- Bots hammering your endpoints thousands of times per second
- Someone writing a script that loops and calls your API non-stop
- Accidental infinite loops in client code
- Running up your OpenWeatherMap API bill

**What the client sees when blocked:**
```json
{ "error": "Too many requests. Please slow down.", "retry_after": "60 seconds" }
```
HTTP 429 status code.

---

### 2. Security Headers — Every Response

Every single response your server sends includes these headers. Think of them as browser instructions.

**`Content-Security-Policy` (CSP)**
The most powerful header. Whitelists exactly which sources can load scripts, styles, and images. If an attacker somehow injects a `<script src="evil.com/malware.js">` into your page, the browser flat-out refuses to load it.

Your policy allows:
- Scripts: only from your own server
- Styles: your server + Google Fonts
- Images: your server + OpenWeatherMap weather icons
- Font files: Google Fonts CDN
- API calls (fetch): only to your own server

**`X-Content-Type-Options: nosniff`**
Stops browsers from "guessing" file types. Without this, a browser might execute a text file as JavaScript if tricked into it.

**`X-Frame-Options: DENY`**
Blocks your app from being embedded in an `<iframe>` on another website. Prevents **clickjacking** — where attackers put your site in an invisible frame and trick users into clicking buttons they can't see.

**`Referrer-Policy: strict-origin-when-cross-origin`**
When users click a link from your app to another site, only your domain name is sent — not the full URL. Prevents leaking search terms or any URL parameters to third parties.

**`Permissions-Policy`**
Restricts which browser APIs can be used. Your app only needs geolocation. Camera, microphone, USB, payment APIs — all explicitly blocked. Even if malicious code was somehow injected, it couldn't access them.

**`Strict-Transport-Security` (HSTS)**
When on HTTPS, tells browsers: "Always use HTTPS for this domain. Never HTTP. Remember this for 1 year." Prevents protocol downgrade attacks.

**Server fingerprint removed**
Flask normally sends `Server: Werkzeug/3.x` in every response — a free advertisement to hackers about exactly what to look up exploits for. We replace it with `Server: Nimbus`.

---

### 3. Input Validation & Sanitization

**All city name inputs are validated before use:**

✅ Allowed: letters (including accented: é, ñ, ü, São Paulo works), spaces, hyphens, apostrophes, commas  
❌ Blocked: `<script>`, `javascript:`, SQL keywords (`DROP TABLE`, `SELECT *`), path traversal (`../`), HTML injection

**City name rules:**
- Minimum 2 characters
- Maximum 100 characters
- Must match allowed character pattern (Unicode-aware regex)
- Dangerous patterns checked and rejected with a clear error

**Coordinate validation:**
- Must be valid numbers (not strings like "hello")
- Latitude must be between -90 and +90
- Longitude must be between -180 and +180
- Cannot be `NaN` or `Infinity`

**Why this matters:**
Without validation, a user could send `city=<script>alert(1)</script>` or `lat=999999999` and potentially cause unexpected behavior or errors that leak internal details.

---

### 4. Request Logging

Every API request is logged with:
- Timestamp
- HTTP method + path
- Response status code
- Caller's IP address
- Request duration (ms)
- User-Agent (first 60 chars)

**Log levels:**
- `INFO` → normal requests (console only)
- `WARNING` → 4xx errors, rate limit hits, suspicious activity (console + file)
- `ERROR/CRITICAL` → server errors (console + file)

**Where logs go:**
- Console: always, all INFO and above
- `weather_app.log` file: WARNING and above (persistent, for production review)

---

### 5. Suspicious Activity Detection

Automatic IP blocking for:

| Trigger | Action |
|---------|--------|
| >10 requests in 1 second (burst) | Block IP for 5 minutes |
| Known scanner User-Agents (sqlmap, nikto, nmap…) | Block IP for 5 minutes |
| Accessing scanner paths (`/.env`, `/wp-admin`, `/.git/config`…) | Block IP for 5 minutes |

**Blocked IP response:**
```json
{ "error": "Your IP has been temporarily blocked due to suspicious activity.", "retry_after": "300 seconds" }
```

**Note:** This is in-memory blocking. If the server restarts, the block list resets. For permanent blocks, use your hosting platform's firewall (Render, Cloudflare, etc.).

---

### 6. Error Hardening

In development, Flask shows full stack traces in the browser when errors occur. This is **extremely dangerous in production** — it shows file paths, variable names, and code structure that attackers can exploit.

We register custom error handlers for all common error codes:

| Code | Response |
|------|----------|
| 400 | `"Bad request. Please check your input."` |
| 404 | `"The requested resource was not found."` |
| 405 | `"HTTP method not allowed for this endpoint."` |
| 429 | `"Too many requests. Please wait before trying again."` |
| 500 | `"An internal error occurred. Please try again later."` |
| Any other | Generic message, full error logged internally |

The real error is **always logged** internally (so you can debug it), but the user only ever sees a clean, generic message.

---

## Production Security Checklist

Before going live, verify:

- [ ] `FLASK_ENV=production` set in Render environment variables
- [ ] `SECRET_KEY` set to a long random string (not the default)
- [ ] `OPENWEATHER_API_KEY` set and working
- [ ] `DEBUG=False` (automatically true when `FLASK_ENV=production`)
- [ ] HTTPS enabled (Render does this for free automatically)
- [ ] Review `weather_app.log` occasionally for suspicious patterns
- [ ] Consider adding Cloudflare (free tier) in front of Render for extra DDoS protection

---

## Upgrading Security Later

**Add Redis for persistent rate limiting** (when you scale to multiple workers):
```python
# In security.py, change storage_uri:
limiter = Limiter(..., storage_uri="redis://localhost:6379")
# Add to requirements.txt: redis==5.0.4
```

**Add Cloudflare** (free, massive DDoS protection):
1. Sign up at cloudflare.com
2. Add your domain
3. Point your domain's DNS to Cloudflare
4. Enable "Under Attack Mode" if you're being targeted

**Add IP allowlisting** (if you only want your own apps to call the API):
```python
ALLOWED_IPS = {"your.office.ip.here"}

@app.before_request
def check_ip():
    if request.path.startswith("/api/") and get_remote_address() not in ALLOWED_IPS:
        return jsonify({"error": "Forbidden"}), 403
```