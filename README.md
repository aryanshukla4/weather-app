# Nimbus Weather App

A responsive weather dashboard built with Flask and the OpenWeatherMap API. Search by city or use your browser location to view current conditions and a five-day forecast.

## Features

- Current weather for any city
- Browser geolocation lookup
- Five-day forecast with daily high, low, humidity, and conditions
- Input validation, rate limiting, security headers, and error handling
- Visitor and search analytics dashboard
- SQLite by default, with optional PostgreSQL support for deployment

## Tech stack

- Python 3.11
- Flask
- Vanilla HTML, CSS, and JavaScript
- OpenWeatherMap API
- SQLite or PostgreSQL

## Getting started

### Prerequisites

- Python 3.11 or later
- An [OpenWeatherMap API key](https://openweathermap.org/api)

### Installation

```bash
git clone https://github.com/<your-username>/<your-repository>.git
cd <your-repository>

python -m venv venv
```

Activate the virtual environment:

```bash
# Windows PowerShell
venv\Scripts\Activate.ps1

# macOS/Linux
source venv/bin/activate
```

Install dependencies and create your local environment file:

```bash
pip install -r requirements.txt
copy .env.example .env      # Windows
# cp .env.example .env      # macOS/Linux
```

Update `.env` with your values:

```env
OPENWEATHER_API_KEY=your_openweathermap_api_key
SECRET_KEY=a-long-random-secret
FLASK_ENV=development

# Optional: protects /admin/visitors with HTTP Basic authentication
ADMIN_USERNAME=admin
ADMIN_PASSWORD=choose-a-strong-password

# Optional: enables PostgreSQL instead of the default SQLite database
# DATABASE_URL=postgresql://USER:PASSWORD@HOST:5432/DBNAME?sslmode=require
```

Run the application:

```bash
python app.py
```

Open [http://localhost:5000](http://localhost:5000).

## API endpoints

| Endpoint | Description |
| --- | --- |
| `GET /api/weather?city=Mumbai` | Current weather by city |
| `GET /api/weather/coords?lat=19.07&lon=72.87` | Current weather by coordinates |
| `GET /api/forecast?city=Mumbai` | Five-day forecast by city |
| `POST /api/track` | Records visitor metadata for analytics |
| `GET /admin/visitors` | Admin analytics dashboard |
| `GET /api/admin/visitors` | Paginated visitor data for the dashboard |

Weather routes are rate-limited. The admin routes are protected only when `ADMIN_PASSWORD` is configured; always configure it in production.

## Deployment

The included `Procfile` starts the app with Gunicorn:

```text
web: gunicorn app:app --workers 2 --bind 0.0.0.0:$PORT
```

Set the environment variables from `.env.example` in your hosting provider. For persistent production analytics, set `DATABASE_URL` to a PostgreSQL database; otherwise the app uses local SQLite.

## Privacy and security

The app records visitor and search data for its analytics dashboard. Review `tracking.md` and `SECURITY.md` before deploying, publish an appropriate privacy notice, and do not commit `.env` files or production database files.

## Project structure

```text
app.py          Flask routes and OpenWeatherMap integration
config.py       Environment-based configuration
security.py     Request protection, validation, and rate limiting
tracker.py      Analytics storage and reporting
templates/      HTML templates
static/         CSS, JavaScript, and image assets
```

## License

No license has been specified for this repository.
