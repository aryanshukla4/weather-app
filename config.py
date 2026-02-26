# ============================================================
# config.py — Central configuration for the app
# ============================================================
# Keeping config separate from app.py means:
#   1. Easy to change settings without touching core logic
#   2. Easy to add different configs for dev vs production
#   3. Clean, organized codebase
# ============================================================

import os

class Config:
    """
    Base configuration.
    All settings are read from environment variables so secrets
    never get hard-coded into the codebase.
    """

    # ── Security ─────────────────────────────────────────────
    SECRET_KEY = os.getenv("SECRET_KEY", "change-this-in-production-please")
    # Flask uses this to sign cookies and sessions.
    # In production, set a long random string as your SECRET_KEY env var.

    # ── OpenWeatherMap API ────────────────────────────────────
    OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY", "")
    # Get a free key at: https://openweathermap.org/api
    # Put it in your .env file as: OPENWEATHER_API_KEY=your_key_here

    # ── Request Settings ──────────────────────────────────────
    REQUEST_TIMEOUT = 10   # seconds before giving up on an API call

    # ── Cache (future feature) ────────────────────────────────
    # Later you can add Redis caching here to avoid hitting the
    # OpenWeatherMap API on every single request.
    # CACHE_TYPE = "redis"
    # CACHE_REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
    # CACHE_DEFAULT_TIMEOUT = 300  # 5 minutes


class DevelopmentConfig(Config):
    """
    Settings only for local development.
    To use: set FLASK_ENV=development in your .env
    """
    DEBUG = True
    TESTING = False


class ProductionConfig(Config):
    """
    Settings for the live deployed website.
    """
    DEBUG = False
    TESTING = False


# This dict lets you select a config by name (used in app.py)
config_map = {
    "development": DevelopmentConfig,
    "production":  ProductionConfig,
}