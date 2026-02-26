# ============================================================
# tracker.py — Visitor Tracking System
# ============================================================
# Captures everything available about each visitor and stores
# it in a local SQLite database (visitors.db).
#
# SQLite = a file-based database built into Python.
# No setup, no server, no extra packages needed.
# The database is just a single file: visitors.db
#
# What we track:
#   - IP address + approximate location (country/city via IP lookup)
#   - Browser, OS, device type (parsed from User-Agent)
#   - Screen resolution, viewport size, pixel ratio
#   - Language, timezone
#   - Referrer (where they came from)
#   - GPS coordinates (only if user clicks "Use My Location")
#   - Visit timestamp
#   - Every city they searched for
# ============================================================

import sqlite3          # built into Python — no pip install needed
import json             # for storing list/dict fields as JSON strings
import re               # regular expressions for User-Agent parsing
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

# ── Database file location ─────────────────────────────────────
DB_PATH = Path(os.getenv("VISITORS_DB_PATH", "visitors.db"))
# This creates visitors.db in your project root folder.
# Path() is better than a plain string — works on Windows & Linux.


# ══════════════════════════════════════════════════════════════
#  DATABASE SETUP
#  Creates the tables if they don't already exist.
#  Safe to call every time the app starts.
# ══════════════════════════════════════════════════════════════

def init_db():
    """
    Creates the database and tables on first run.
    Uses "IF NOT EXISTS" so it's safe to call every startup —
    it won't wipe data if the table already exists.
    """
    conn = get_connection()
    cursor = conn.cursor()

    # ── Table 1: visitors ──────────────────────────────────────
    # One row per page visit.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS visitors (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            -- AUTOINCREMENT = SQLite auto-assigns 1, 2, 3... for each row

            visit_time        TEXT NOT NULL,
            -- ISO timestamp e.g. "2025-07-15T14:32:01Z"

            ip_address        TEXT,
            -- The visitor's IP. Could be IPv4 or IPv6.

            ip_country        TEXT,
            ip_country_code   TEXT,
            ip_region         TEXT,
            ip_city           TEXT,
            ip_isp            TEXT,
            ip_org            TEXT,
            -- These come from a free IP geolocation API
            -- e.g. country="India", city="Mumbai", isp="Jio"

            user_agent        TEXT,
            -- Full browser string

            browser_name      TEXT,
            browser_version   TEXT,
            os_name           TEXT,
            os_version        TEXT,
            device_type       TEXT,
            -- "desktop", "mobile", or "tablet"
            -- Parsed from user_agent string

            browser_language  TEXT,
            languages         TEXT,
            timezone          TEXT,
            timezone_offset   INTEGER,
            platform          TEXT,

            screen_width      INTEGER,
            screen_height     INTEGER,
            viewport_width    INTEGER,
            viewport_height   INTEGER,
            color_depth       INTEGER,
            pixel_ratio       REAL,

            is_touch_device   INTEGER,
            -- SQLite has no boolean type. We store 0 or 1.

            cookies_enabled   INTEGER,
            connection_type   TEXT,

            referrer          TEXT,
            page_url          TEXT,
            local_time        TEXT,

            location_granted  INTEGER DEFAULT 0,
            -- Did the user click "Use My Location" and allow it?

            lat               REAL,
            lon               REAL,
            accuracy_meters   REAL,
            -- GPS accuracy in meters (e.g. 20 = within 20 meters)

            raw_data          TEXT
            -- Full JSON of everything sent — future-proof backup
        )
    """)

    # ── Table 2: searches ──────────────────────────────────────
    # One row per city search. Links back to visitors via visitor_id.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS searches (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            visitor_id  INTEGER,
            -- REFERENCES visitors(id) would be a foreign key
            -- but SQLite doesn't enforce it by default

            search_time TEXT NOT NULL,
            ip_address  TEXT,
            city_query  TEXT,
            -- The city the user typed/clicked

            FOREIGN KEY (visitor_id) REFERENCES visitors(id)
        )
    """)

    # ── Index: fast lookup by IP and time ──────────────────────
    # Without indexes, SQLite scans every row.
    # With indexes, it jumps straight to matching rows (much faster).
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_visitors_ip
        ON visitors(ip_address)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_visitors_time
        ON visitors(visit_time)
    """)

    conn.commit()
    conn.close()
    logging.info("Database initialized ✓")


def get_connection() -> sqlite3.Connection:
    """
    Opens and returns a database connection.
    check_same_thread=False is needed for Flask because Flask
    can serve requests from multiple threads.
    """
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    # row_factory = sqlite3.Row makes results accessible like dicts:
    # row["city"] instead of row[4]
    return conn


# ══════════════════════════════════════════════════════════════
#  IP GEOLOCATION
#  Maps an IP address to a country, city, and ISP.
#  Uses ip-api.com — free, no API key needed, 45 req/min limit.
# ══════════════════════════════════════════════════════════════

def get_ip_info(ip: str) -> dict:
    """
    Looks up geographic info for an IP address.
    Returns a dict with country, city, ISP, etc.
    Returns empty dict if the lookup fails.
    """
    import requests as req

    # Skip lookup for private/local IPs
    # These are IPs that only exist on local networks — no geo data available
    private_prefixes = ("127.", "192.168.", "10.", "172.", "::1", "localhost")
    if any(ip.startswith(p) for p in private_prefixes):
        return {"ip_city": "Local", "ip_country": "Local Network"}

    try:
        # ip-api.com is free, no key needed, returns JSON
        # Fields parameter limits what we get back (faster response)
        response = req.get(
            f"http://ip-api.com/json/{ip}",
            params={"fields": "status,country,countryCode,regionName,city,isp,org"},
            timeout=3
            # timeout=3 seconds — if slow, skip it rather than delay the user
        )
        data = response.json()

        if data.get("status") == "success":
            return {
                "ip_country":      data.get("country", ""),
                "ip_country_code": data.get("countryCode", ""),
                "ip_region":       data.get("regionName", ""),
                "ip_city":         data.get("city", ""),
                "ip_isp":          data.get("isp", ""),
                "ip_org":          data.get("org", ""),
            }
    except Exception as e:
        logging.debug(f"IP lookup failed for {ip}: {e}")

    return {}


# ══════════════════════════════════════════════════════════════
#  USER AGENT PARSER
#  Extracts browser name, version, OS, and device type from
#  the User-Agent string without any external libraries.
# ══════════════════════════════════════════════════════════════

def parse_user_agent(ua: str) -> dict:
    """
    Parses the User-Agent string to extract human-readable info.
    User-Agent strings look like:
      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36
       (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"

    We use regex to pick out the important parts.
    """

    if not ua:
        return {"browser_name": "Unknown", "os_name": "Unknown", "device_type": "unknown"}

    result = {}

    # ── Device type ────────────────────────────────────────────
    ua_lower = ua.lower()
    if any(x in ua_lower for x in ["iphone", "android", "mobile", "blackberry", "opera mini"]):
        result["device_type"] = "mobile"
    elif any(x in ua_lower for x in ["ipad", "tablet", "kindle"]):
        result["device_type"] = "tablet"
    else:
        result["device_type"] = "desktop"

    # ── OS ─────────────────────────────────────────────────────
    if "windows nt 10" in ua_lower:
        result["os_name"] = "Windows 10/11"
    elif "windows nt 6.3" in ua_lower:
        result["os_name"] = "Windows 8.1"
    elif "windows nt 6.1" in ua_lower:
        result["os_name"] = "Windows 7"
    elif "windows" in ua_lower:
        result["os_name"] = "Windows"
    elif "mac os x" in ua_lower:
        # Extract version: "Mac OS X 10_15_7" → "10.15.7"
        m = re.search(r"mac os x ([\d_]+)", ua_lower)
        version = m.group(1).replace("_", ".") if m else ""
        result["os_name"] = f"macOS {version}".strip()
    elif "android" in ua_lower:
        m = re.search(r"android ([\d.]+)", ua_lower)
        version = m.group(1) if m else ""
        result["os_name"] = f"Android {version}".strip()
    elif "iphone os" in ua_lower or "ipad" in ua_lower:
        m = re.search(r"os ([\d_]+)", ua_lower)
        version = m.group(1).replace("_", ".") if m else ""
        result["os_name"] = f"iOS {version}".strip()
    elif "linux" in ua_lower:
        result["os_name"] = "Linux"
    else:
        result["os_name"] = "Unknown OS"

    # ── Browser ────────────────────────────────────────────────
    # Order matters! Check Edge before Chrome (Edge also has "Chrome" in its UA)
    if "edg/" in ua_lower or "edge/" in ua_lower:
        m = re.search(r"edg(?:e)?/([\d.]+)", ua_lower)
        result["browser_name"]    = "Microsoft Edge"
        result["browser_version"] = m.group(1) if m else ""
    elif "opr/" in ua_lower or "opera" in ua_lower:
        m = re.search(r"(?:opr|opera)/([\d.]+)", ua_lower)
        result["browser_name"]    = "Opera"
        result["browser_version"] = m.group(1) if m else ""
    elif "firefox/" in ua_lower:
        m = re.search(r"firefox/([\d.]+)", ua_lower)
        result["browser_name"]    = "Firefox"
        result["browser_version"] = m.group(1) if m else ""
    elif "chrome/" in ua_lower:
        m = re.search(r"chrome/([\d.]+)", ua_lower)
        result["browser_name"]    = "Chrome"
        result["browser_version"] = m.group(1) if m else ""
    elif "safari/" in ua_lower:
        m = re.search(r"version/([\d.]+)", ua_lower)
        result["browser_name"]    = "Safari"
        result["browser_version"] = m.group(1) if m else ""
    else:
        result["browser_name"]    = "Other"
        result["browser_version"] = ""

    return result


# ══════════════════════════════════════════════════════════════
#  SAVE VISITOR
#  Main function called from app.py when /api/track is hit.
# ══════════════════════════════════════════════════════════════

def save_visitor(data: dict, ip: str) -> int:
    """
    Saves a visitor record to the database.

    Parameters:
        data — the JSON body sent from the browser (app.js trackVisitor())
        ip   — the visitor's IP address (from Flask request object)

    Returns:
        The new row's ID (integer) — useful for linking searches later.
    """

    # Look up geographic info from the IP
    ip_info = get_ip_info(ip)

    # Parse browser/OS/device from User-Agent
    ua_info = parse_user_agent(data.get("user_agent", ""))

    now = datetime.now(timezone.utc).isoformat()
    # isoformat() → "2025-07-15T14:32:01+00:00" — standard timestamp format

    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            INSERT INTO visitors (
                visit_time, ip_address,
                ip_country, ip_country_code, ip_region, ip_city, ip_isp, ip_org,
                user_agent, browser_name, browser_version, os_name, os_version, device_type,
                browser_language, languages, timezone, timezone_offset, platform,
                screen_width, screen_height, viewport_width, viewport_height,
                color_depth, pixel_ratio, is_touch_device, cookies_enabled, connection_type,
                referrer, page_url, local_time,
                location_granted, lat, lon, accuracy_meters,
                raw_data
            ) VALUES (
                ?, ?,
                ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?, ?, ?, ?,
                ?, ?, ?,
                ?, ?, ?, ?,
                ?
            )
        """, (
            now,                              ip,
            ip_info.get("ip_country", ""),    ip_info.get("ip_country_code", ""),
            ip_info.get("ip_region", ""),     ip_info.get("ip_city", ""),
            ip_info.get("ip_isp", ""),        ip_info.get("ip_org", ""),

            data.get("user_agent", ""),
            ua_info.get("browser_name", ""),  ua_info.get("browser_version", ""),
            ua_info.get("os_name", ""),       ua_info.get("os_version", ""),
            ua_info.get("device_type", ""),

            data.get("browser_language", ""), data.get("languages", ""),
            data.get("timezone", ""),         data.get("timezone_offset"),
            data.get("platform", ""),

            data.get("screen_width"),         data.get("screen_height"),
            data.get("viewport_width"),       data.get("viewport_height"),
            data.get("color_depth"),          data.get("pixel_ratio"),
            int(data.get("is_touch_device", False)),
            int(data.get("cookies_enabled", True)),
            data.get("connection_type", ""),

            data.get("referrer", ""),         data.get("page_url", ""),
            data.get("local_time", ""),

            int(data.get("location_granted", False)),
            data.get("lat"),                  data.get("lon"),
            data.get("accuracy_meters"),

            json.dumps(data),   # store full raw data as JSON string
        ))

        conn.commit()
        visitor_id = cursor.lastrowid
        # lastrowid = the auto-assigned ID of the row we just inserted

        logging.info(
            f"VISITOR_TRACKED | ID={visitor_id} | IP={ip} | "
            f"City={ip_info.get('ip_city','?')} | "
            f"Browser={ua_info.get('browser_name','?')} | "
            f"Device={ua_info.get('device_type','?')} | "
            f"GPS={'yes' if data.get('location_granted') else 'no'}"
        )
        return visitor_id

    except Exception as e:
        logging.error(f"Failed to save visitor: {e}")
        conn.rollback()
        return -1
    finally:
        conn.close()


def save_search(ip: str, city: str, visitor_id: int = None):
    """
    Saves a city search event to the searches table.
    Called from app.py when /api/weather is hit.
    """
    conn = get_connection()
    try:
        conn.execute("""
            INSERT INTO searches (visitor_id, search_time, ip_address, city_query)
            VALUES (?, ?, ?, ?)
        """, (visitor_id, datetime.now(timezone.utc).isoformat(), ip, city))
        conn.commit()
    except Exception as e:
        logging.error(f"Failed to save search: {e}")
    finally:
        conn.close()


# ══════════════════════════════════════════════════════════════
#  ANALYTICS QUERIES
#  These are called by the /admin/visitors route in app.py
#  to build the admin dashboard.
# ══════════════════════════════════════════════════════════════

def get_visitor_stats() -> dict:
    """
    Returns summary statistics for the admin dashboard:
    - Total unique visitors
    - Visitors today
    - Top countries
    - Top browsers
    - Top devices
    - Top cities searched
    - Location permission grant rate
    - Recent visitors list
    """
    conn = get_connection()

    try:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        # strftime formats the date as "2025-07-15"

        # Total all-time visitors
        total = conn.execute("SELECT COUNT(*) FROM visitors").fetchone()[0]

        # Visitors today
        today_count = conn.execute(
            "SELECT COUNT(*) FROM visitors WHERE visit_time LIKE ?",
            (f"{today}%",)
            # LIKE "2025-07-15%" matches any time on that date
        ).fetchone()[0]

        # Top 5 countries
        countries = conn.execute("""
            SELECT ip_country, COUNT(*) as count
            FROM visitors
            WHERE ip_country != '' AND ip_country != 'Local Network'
            GROUP BY ip_country
            ORDER BY count DESC
            LIMIT 5
        """).fetchall()
        # GROUP BY collapses all rows with the same country into one row
        # ORDER BY count DESC = most common first

        # Top 5 browsers
        browsers = conn.execute("""
            SELECT browser_name, COUNT(*) as count
            FROM visitors
            WHERE browser_name != ''
            GROUP BY browser_name
            ORDER BY count DESC
            LIMIT 5
        """).fetchall()

        # Device breakdown
        devices = conn.execute("""
            SELECT device_type, COUNT(*) as count
            FROM visitors
            GROUP BY device_type
            ORDER BY count DESC
        """).fetchall()

        # Top 10 searched cities
        top_searches = conn.execute("""
            SELECT city_query, COUNT(*) as count
            FROM searches
            GROUP BY city_query
            ORDER BY count DESC
            LIMIT 10
        """).fetchall()

        # Location permission rate
        gps_granted = conn.execute(
            "SELECT COUNT(*) FROM visitors WHERE location_granted = 1"
        ).fetchone()[0]

        gps_rate = round((gps_granted / total * 100), 1) if total > 0 else 0

        # 20 most recent visitors (newest first)
        recent = conn.execute("""
            SELECT visit_time, ip_address, ip_city, ip_country,
                   browser_name, device_type, location_granted, lat, lon,
                   timezone, screen_width, screen_height
            FROM visitors
            ORDER BY id DESC
            LIMIT 20
        """).fetchall()

        return {
            "total":        total,
            "today":        today_count,
            "countries":    [dict(r) for r in countries],
            "browsers":     [dict(r) for r in browsers],
            "devices":      [dict(r) for r in devices],
            "top_searches": [dict(r) for r in top_searches],
            "gps_rate":     gps_rate,
            "gps_granted":  gps_granted,
            "recent":       [dict(r) for r in recent],
        }

    finally:
        conn.close()
