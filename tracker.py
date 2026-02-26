import json
import logging
import os
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import psycopg
    from psycopg.rows import dict_row
except Exception:  # pragma: no cover
    psycopg = None
    dict_row = None


SQLITE_DB_PATH = Path(os.getenv("VISITORS_DB_PATH", "visitors.db"))
_coords_lookup_cache: dict[tuple[float, float], dict[str, Any]] = {}


def _database_url() -> str:
    raw = (os.getenv("DATABASE_URL") or "").strip()
    if raw.startswith("postgres://"):
        return "postgresql://" + raw[len("postgres://") :]
    return raw


def _using_postgres() -> bool:
    return bool(_database_url())


def get_connection():
    if _using_postgres():
        if psycopg is None:
            raise RuntimeError("DATABASE_URL is set but psycopg is not installed.")
        return psycopg.connect(_database_url(), connect_timeout=10)

    SQLITE_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(SQLITE_DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    cur = conn.cursor()
    try:
        if _using_postgres():
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS visitors (
                    id BIGSERIAL PRIMARY KEY,
                    visit_time TEXT NOT NULL,
                    ip_address TEXT,
                    ip_country TEXT,
                    ip_country_code TEXT,
                    ip_region TEXT,
                    ip_city TEXT,
                    ip_isp TEXT,
                    ip_org TEXT,
                    user_agent TEXT,
                    browser_name TEXT,
                    browser_version TEXT,
                    os_name TEXT,
                    os_version TEXT,
                    device_type TEXT,
                    browser_language TEXT,
                    languages TEXT,
                    timezone TEXT,
                    timezone_offset INTEGER,
                    platform TEXT,
                    screen_width INTEGER,
                    screen_height INTEGER,
                    viewport_width INTEGER,
                    viewport_height INTEGER,
                    color_depth INTEGER,
                    pixel_ratio DOUBLE PRECISION,
                    is_touch_device INTEGER,
                    cookies_enabled INTEGER,
                    connection_type TEXT,
                    referrer TEXT,
                    page_url TEXT,
                    local_time TEXT,
                    location_granted INTEGER DEFAULT 0,
                    lat DOUBLE PRECISION,
                    lon DOUBLE PRECISION,
                    accuracy_meters DOUBLE PRECISION,
                    raw_data TEXT
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS searches (
                    id BIGSERIAL PRIMARY KEY,
                    visitor_id BIGINT REFERENCES visitors(id),
                    search_time TEXT NOT NULL,
                    ip_address TEXT,
                    city_query TEXT
                )
                """
            )
            cur.execute("CREATE INDEX IF NOT EXISTS idx_visitors_ip ON visitors(ip_address)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_visitors_time ON visitors(visit_time)")
        else:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS visitors (
                    id                INTEGER PRIMARY KEY AUTOINCREMENT,
                    visit_time        TEXT NOT NULL,
                    ip_address        TEXT,
                    ip_country        TEXT,
                    ip_country_code   TEXT,
                    ip_region         TEXT,
                    ip_city           TEXT,
                    ip_isp            TEXT,
                    ip_org            TEXT,
                    user_agent        TEXT,
                    browser_name      TEXT,
                    browser_version   TEXT,
                    os_name           TEXT,
                    os_version        TEXT,
                    device_type       TEXT,
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
                    cookies_enabled   INTEGER,
                    connection_type   TEXT,
                    referrer          TEXT,
                    page_url          TEXT,
                    local_time        TEXT,
                    location_granted  INTEGER DEFAULT 0,
                    lat               REAL,
                    lon               REAL,
                    accuracy_meters   REAL,
                    raw_data          TEXT
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS searches (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    visitor_id  INTEGER,
                    search_time TEXT NOT NULL,
                    ip_address  TEXT,
                    city_query  TEXT,
                    FOREIGN KEY (visitor_id) REFERENCES visitors(id)
                )
                """
            )
            cur.execute("CREATE INDEX IF NOT EXISTS idx_visitors_ip ON visitors(ip_address)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_visitors_time ON visitors(visit_time)")

        conn.commit()
        logging.info("Tracking DB initialized")
    finally:
        conn.close()


def get_ip_info(ip: str) -> dict[str, Any]:
    import requests as req

    private_prefixes = ("127.", "192.168.", "10.", "172.", "::1", "localhost")
    if not ip or any(ip.startswith(p) for p in private_prefixes):
        return {"ip_city": "Local", "ip_country": "Local Network"}

    try:
        response = req.get(
            f"http://ip-api.com/json/{ip}",
            params={"fields": "status,country,countryCode,regionName,city,isp,org"},
            timeout=3,
        )
        data = response.json()
        if data.get("status") == "success":
            return {
                "ip_country": data.get("country", ""),
                "ip_country_code": data.get("countryCode", ""),
                "ip_region": data.get("regionName", ""),
                "ip_city": data.get("city", ""),
                "ip_isp": data.get("isp", ""),
                "ip_org": data.get("org", ""),
            }
    except Exception as e:
        logging.debug("IP lookup failed for %s: %s", ip, e)

    return {}


def get_geo_from_coords(lat: Any, lon: Any) -> dict[str, Any]:
    """
    Reverse geocode GPS coordinates to city/state/country.
    Returns keys aligned with visitor storage fields.
    """
    try:
        lat_f = float(lat)
        lon_f = float(lon)
    except (TypeError, ValueError):
        return {}

    cache_key = (round(lat_f, 3), round(lon_f, 3))
    if cache_key in _coords_lookup_cache:
        return dict(_coords_lookup_cache[cache_key])

    import requests as req

    result: dict[str, Any] = {}

    # First try OpenWeather reverse geocoding (uses existing API key).
    api_key = (os.getenv("OPENWEATHER_API_KEY") or "").strip()
    if api_key:
        try:
            response = req.get(
                "https://api.openweathermap.org/geo/1.0/reverse",
                params={"lat": lat_f, "lon": lon_f, "limit": 1, "appid": api_key},
                timeout=3,
            )
            response.raise_for_status()
            data = response.json()
            if isinstance(data, list) and data:
                item = data[0]
                result = {
                    "ip_city": item.get("name", "") or "",
                    "ip_region": item.get("state", "") or "",
                    # OpenWeather returns 2-letter country code here.
                    "ip_country": item.get("country", "") or "",
                    "ip_country_code": item.get("country", "") or "",
                }
        except Exception as e:
            logging.debug("OpenWeather reverse geocode failed: %s", e)

    # Fallback: Nominatim for richer country/state names when needed.
    if not result.get("ip_city") or not result.get("ip_region"):
        try:
            response = req.get(
                "https://nominatim.openstreetmap.org/reverse",
                params={"format": "jsonv2", "lat": lat_f, "lon": lon_f, "zoom": 10},
                headers={"User-Agent": "NimbusWeatherApp/1.0"},
                timeout=3,
            )
            response.raise_for_status()
            payload = response.json()
            addr = payload.get("address", {}) if isinstance(payload, dict) else {}
            city = addr.get("city") or addr.get("town") or addr.get("village") or addr.get("hamlet") or ""
            state = addr.get("state") or addr.get("region") or ""
            country = addr.get("country") or ""
            country_code = (addr.get("country_code") or "").upper()
            if city and not result.get("ip_city"):
                result["ip_city"] = city
            if state and not result.get("ip_region"):
                result["ip_region"] = state
            if country and not result.get("ip_country"):
                result["ip_country"] = country
            if country_code and not result.get("ip_country_code"):
                result["ip_country_code"] = country_code
        except Exception as e:
            logging.debug("Nominatim reverse geocode failed: %s", e)

    if result:
        _coords_lookup_cache[cache_key] = dict(result)
    return result


def parse_user_agent(ua: str) -> dict[str, str]:
    if not ua:
        return {"browser_name": "Unknown", "os_name": "Unknown", "device_type": "unknown"}

    result: dict[str, str] = {}
    ua_lower = ua.lower()

    if any(x in ua_lower for x in ["iphone", "android", "mobile", "blackberry", "opera mini"]):
        result["device_type"] = "mobile"
    elif any(x in ua_lower for x in ["ipad", "tablet", "kindle"]):
        result["device_type"] = "tablet"
    else:
        result["device_type"] = "desktop"

    if "windows nt 10" in ua_lower:
        result["os_name"] = "Windows 10/11"
    elif "windows nt 6.3" in ua_lower:
        result["os_name"] = "Windows 8.1"
    elif "windows nt 6.1" in ua_lower:
        result["os_name"] = "Windows 7"
    elif "windows" in ua_lower:
        result["os_name"] = "Windows"
    elif "mac os x" in ua_lower:
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

    if "edg/" in ua_lower or "edge/" in ua_lower:
        m = re.search(r"edg(?:e)?/([\d.]+)", ua_lower)
        result["browser_name"] = "Microsoft Edge"
        result["browser_version"] = m.group(1) if m else ""
    elif "opr/" in ua_lower or "opera" in ua_lower:
        m = re.search(r"(?:opr|opera)/([\d.]+)", ua_lower)
        result["browser_name"] = "Opera"
        result["browser_version"] = m.group(1) if m else ""
    elif "firefox/" in ua_lower:
        m = re.search(r"firefox/([\d.]+)", ua_lower)
        result["browser_name"] = "Firefox"
        result["browser_version"] = m.group(1) if m else ""
    elif "chrome/" in ua_lower:
        m = re.search(r"chrome/([\d.]+)", ua_lower)
        result["browser_name"] = "Chrome"
        result["browser_version"] = m.group(1) if m else ""
    elif "safari/" in ua_lower:
        m = re.search(r"version/([\d.]+)", ua_lower)
        result["browser_name"] = "Safari"
        result["browser_version"] = m.group(1) if m else ""
    else:
        result["browser_name"] = "Other"
        result["browser_version"] = ""

    return result


def _dict_rows(rows: list[Any]) -> list[dict[str, Any]]:
    return [dict(r) for r in rows]


def save_visitor(data: dict, ip: str) -> int:
    ip_info = get_ip_info(ip)
    if data.get("location_granted") and data.get("lat") is not None and data.get("lon") is not None:
        gps_info = get_geo_from_coords(data.get("lat"), data.get("lon"))
        if gps_info:
            ip_info.update({k: v for k, v in gps_info.items() if v})

    ua_info = parse_user_agent(data.get("user_agent", ""))
    now = datetime.now(timezone.utc).isoformat()

    values = (
        now,
        ip,
        ip_info.get("ip_country", ""),
        ip_info.get("ip_country_code", ""),
        ip_info.get("ip_region", ""),
        ip_info.get("ip_city", ""),
        ip_info.get("ip_isp", ""),
        ip_info.get("ip_org", ""),
        data.get("user_agent", ""),
        ua_info.get("browser_name", ""),
        ua_info.get("browser_version", ""),
        ua_info.get("os_name", ""),
        ua_info.get("os_version", ""),
        ua_info.get("device_type", ""),
        data.get("browser_language", ""),
        data.get("languages", ""),
        data.get("timezone", ""),
        data.get("timezone_offset"),
        data.get("platform", ""),
        data.get("screen_width"),
        data.get("screen_height"),
        data.get("viewport_width"),
        data.get("viewport_height"),
        data.get("color_depth"),
        data.get("pixel_ratio"),
        int(data.get("is_touch_device", False)),
        int(data.get("cookies_enabled", True)),
        data.get("connection_type", ""),
        data.get("referrer", ""),
        data.get("page_url", ""),
        data.get("local_time", ""),
        int(data.get("location_granted", False)),
        data.get("lat"),
        data.get("lon"),
        data.get("accuracy_meters"),
        json.dumps(data),
    )

    conn = get_connection()
    try:
        if _using_postgres():
            cur = conn.cursor(row_factory=dict_row)
            cur.execute(
                """
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
                    %s, %s,
                    %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s, %s,
                    %s
                ) RETURNING id
                """,
                values,
            )
            visitor_id = int(cur.fetchone()["id"])
        else:
            cur = conn.cursor()
            cur.execute(
                """
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
                """,
                values,
            )
            visitor_id = int(cur.lastrowid)

        conn.commit()
        return visitor_id
    except Exception as e:
        logging.error("Failed to save visitor: %s", e)
        conn.rollback()
        return -1
    finally:
        conn.close()


def save_search(ip: str, city: str, visitor_id: int = None):
    conn = get_connection()
    now = datetime.now(timezone.utc).isoformat()
    try:
        if _using_postgres():
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO searches (visitor_id, search_time, ip_address, city_query)
                VALUES (%s, %s, %s, %s)
                """,
                (visitor_id, now, ip, city),
            )
        else:
            conn.execute(
                """
                INSERT INTO searches (visitor_id, search_time, ip_address, city_query)
                VALUES (?, ?, ?, ?)
                """,
                (visitor_id, now, ip, city),
            )
        conn.commit()
    except Exception as e:
        logging.error("Failed to save search: %s", e)
    finally:
        conn.close()


def get_visitor_stats() -> dict[str, Any]:
    conn = get_connection()
    try:
        if _using_postgres():
            cur = conn.cursor(row_factory=dict_row)

            cur.execute("SELECT COUNT(*) AS c FROM visitors")
            total = int(cur.fetchone()["c"])

            today_prefix = datetime.now(timezone.utc).strftime("%Y-%m-%d") + "%"
            cur.execute("SELECT COUNT(*) AS c FROM visitors WHERE visit_time LIKE %s", (today_prefix,))
            today_count = int(cur.fetchone()["c"])

            cur.execute(
                """
                SELECT ip_country, COUNT(*) as count
                FROM visitors
                WHERE ip_country != '' AND ip_country != 'Local Network'
                GROUP BY ip_country
                ORDER BY count DESC
                LIMIT 5
                """
            )
            countries = cur.fetchall()

            cur.execute(
                """
                SELECT browser_name, COUNT(*) as count
                FROM visitors
                WHERE browser_name != ''
                GROUP BY browser_name
                ORDER BY count DESC
                LIMIT 5
                """
            )
            browsers = cur.fetchall()

            cur.execute(
                """
                SELECT device_type, COUNT(*) as count
                FROM visitors
                GROUP BY device_type
                ORDER BY count DESC
                """
            )
            devices = cur.fetchall()

            cur.execute(
                """
                SELECT city_query, COUNT(*) as count
                FROM searches
                GROUP BY city_query
                ORDER BY count DESC
                LIMIT 10
                """
            )
            top_searches = cur.fetchall()

            cur.execute("SELECT COUNT(*) AS c FROM visitors WHERE location_granted = 1")
            gps_granted = int(cur.fetchone()["c"])

            cur.execute(
                """
                SELECT visit_time, ip_address, ip_city, ip_region, ip_country,
                       browser_name, os_name, device_type, location_granted, lat, lon,
                       timezone, screen_width, screen_height
                FROM visitors
                ORDER BY id DESC
                LIMIT 100
                """
            )
            recent = cur.fetchall()
        else:
            total = conn.execute("SELECT COUNT(*) FROM visitors").fetchone()[0]
            today_prefix = datetime.now(timezone.utc).strftime("%Y-%m-%d") + "%"
            today_count = conn.execute(
                "SELECT COUNT(*) FROM visitors WHERE visit_time LIKE ?",
                (today_prefix,),
            ).fetchone()[0]
            countries = conn.execute(
                """
                SELECT ip_country, COUNT(*) as count
                FROM visitors
                WHERE ip_country != '' AND ip_country != 'Local Network'
                GROUP BY ip_country
                ORDER BY count DESC
                LIMIT 5
                """
            ).fetchall()
            browsers = conn.execute(
                """
                SELECT browser_name, COUNT(*) as count
                FROM visitors
                WHERE browser_name != ''
                GROUP BY browser_name
                ORDER BY count DESC
                LIMIT 5
                """
            ).fetchall()
            devices = conn.execute(
                """
                SELECT device_type, COUNT(*) as count
                FROM visitors
                GROUP BY device_type
                ORDER BY count DESC
                """
            ).fetchall()
            top_searches = conn.execute(
                """
                SELECT city_query, COUNT(*) as count
                FROM searches
                GROUP BY city_query
                ORDER BY count DESC
                LIMIT 10
                """
            ).fetchall()
            gps_granted = conn.execute(
                "SELECT COUNT(*) FROM visitors WHERE location_granted = 1"
            ).fetchone()[0]
            recent = conn.execute(
                """
                SELECT visit_time, ip_address, ip_city, ip_region, ip_country,
                       browser_name, os_name, device_type, location_granted, lat, lon,
                       timezone, screen_width, screen_height
                FROM visitors
                ORDER BY id DESC
                LIMIT 100
                """
            ).fetchall()

        gps_rate = round((gps_granted / total * 100), 1) if total > 0 else 0

        return {
            "total": int(total),
            "today": int(today_count),
            "countries": _dict_rows(countries),
            "browsers": _dict_rows(browsers),
            "devices": _dict_rows(devices),
            "top_searches": _dict_rows(top_searches),
            "gps_rate": gps_rate,
            "gps_granted": int(gps_granted),
            "recent": _dict_rows(recent),
        }
    finally:
        conn.close()
