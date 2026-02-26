# 🌤 Nimbus Weather App — Complete Guide
### From Zero to Live Website

---

## 📁 Project Structure

```
weather-app/
├── app.py              ← Python Flask backend (main server)
├── config.py           ← App configuration & settings
├── requirements.txt    ← Python package dependencies
├── Procfile            ← Tells deployment platform how to start app
├── runtime.txt         ← Python version for deployment
├── .env.example        ← Template for your secret keys
├── .env                ← YOUR actual secrets (never commit this!)
├── .gitignore          ← Files Git should ignore
│
├── templates/
│   └── index.html      ← The webpage (Flask serves this)
│
└── static/
    ├── css/
    │   └── style.css   ← All visual styling
    └── js/
        └── app.js      ← Frontend logic (talks to your Python API)
```

---

## 🗺 How It All Works Together

```
[Browser] ──search "Mumbai"──► [JavaScript in app.js]
                                        │
                            fetch("/api/weather?city=Mumbai")
                                        │
                                        ▼
                              [Flask in app.py]
                                        │
                      requests.get(OpenWeatherMap API)
                                        │
                                        ▼
                              [OpenWeatherMap API]
                              returns raw JSON data
                                        │
                                        ▼
                              [Flask parses & cleans data]
                                        │
                              returns clean JSON to browser
                                        │
                                        ▼
                          [JavaScript renders HTML page]
                          (temperature, humidity, forecast, etc.)
```

---

## ✅ STEP 1 — Get Your Free API Key

1. Go to **https://openweathermap.org**
2. Click **Sign Up** (top right)
3. Fill in your details and verify your email
4. Go to **My Account → API keys**
5. Copy the default key (looks like: `a1b2c3d4e5f6g7h8i9j0...`)
6. ⚠️ **Wait ~10 minutes** after signup — new keys need time to activate

---

## ✅ STEP 2 — Install Python

- Download Python 3.11+ from **https://python.org/downloads**
- During installation on Windows, **check "Add Python to PATH"**
- Verify: open terminal and type `python --version`

---

## ✅ STEP 3 — Set Up the Project Locally

Open your terminal and run these commands one by one:

```bash
# 1. Navigate to where you want the project
cd Desktop

# 2. Create the project folder
mkdir weather-app
cd weather-app

# Copy all the provided files into this folder
# (app.py, config.py, requirements.txt, etc.)

# 3. Create a Python virtual environment
# A venv is an isolated Python sandbox — keeps this project's
# packages separate from other Python projects on your machine.
python -m venv venv

# 4. Activate the virtual environment
# On Mac/Linux:
source venv/bin/activate
# On Windows:
venv\Scripts\activate

# You'll see (venv) appear at the start of your terminal prompt.
# That means the venv is active. ✓

# 5. Install all required packages
pip install -r requirements.txt
# This reads requirements.txt and installs Flask, requests, etc.
```

---

## ✅ STEP 4 — Create Your .env File

```bash
# Copy the template
cp .env.example .env
```

Now open `.env` in any text editor and fill it in:

```env
OPENWEATHER_API_KEY=paste_your_key_here
SECRET_KEY=any-long-random-string-you-make-up
FLASK_ENV=development
```

---

## ✅ STEP 5 — Run the App Locally

```bash
# Make sure your venv is activated, then:
python app.py
```

You'll see output like:
```
 * Running on http://127.0.0.1:5000
 * Debug mode: on
```

Open your browser and visit: **http://localhost:5000**

🎉 Your weather app is running locally!

---

## ✅ STEP 6 — Push to GitHub

GitHub stores your code and connects to Render for deployment.

```bash
# 1. Initialize Git in your project folder
git init

# 2. Stage all files (except .env, which .gitignore blocks)
git add .

# 3. Make your first commit
git commit -m "Initial weather app"

# 4. Go to https://github.com → New repository → name it "weather-app"
# → Do NOT initialize with README (we already have code)
# → Create repository

# 5. Connect local repo to GitHub (replace YOUR_USERNAME)
git remote add origin https://github.com/YOUR_USERNAME/weather-app.git

# 6. Push your code to GitHub
git branch -M main
git push -u origin main
```

---

## ✅ STEP 7 — Deploy on Render (Free)

Render is the easiest way to deploy a Python web app for free.

1. Go to **https://render.com** and sign up with your GitHub account
2. Click **New → Web Service**
3. Click **Connect** next to your `weather-app` repository
4. Fill in the settings:
   - **Name**: `nimbus-weather` (or anything you like)
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app --workers 2 --bind 0.0.0.0:$PORT`
5. Click **Add Environment Variables** and add:
   - `OPENWEATHER_API_KEY` = your key
   - `SECRET_KEY` = any random string
   - `FLASK_ENV` = `production`
6. Click **Create Web Service**

⏳ Wait 2-3 minutes while Render builds and deploys your app.

Your live URL will be something like: `https://nimbus-weather.onrender.com`

---

## ✅ STEP 8 — Every Time You Update the App

```bash
# Make your code changes, then:
git add .
git commit -m "describe what you changed"
git push
```

Render detects the push and **automatically redeploys** your app. ✓

---

## 🔮 Future Features You Can Add

The app is designed so adding features is straightforward:

### 🗺 Weather Map
Add a new route in `app.py`:
```python
@app.route("/api/radar")
def get_radar():
    return jsonify({"tile_url": f"https://tile.openweathermap.org/map/precipitation_new/..."})
```

### ⚡ Caching (Reduce API Calls)
```bash
pip install flask-caching
```
Add to `app.py`:
```python
from flask_caching import Cache
cache = Cache(app, config={"CACHE_TYPE": "simple"})

@cache.cached(timeout=300, query_string=True)  # Cache for 5 minutes
@app.route("/api/weather")
def get_weather():
    ...
```

### 🚨 Rate Limiting (Prevent Abuse)
```bash
pip install flask-limiter
```
```python
from flask_limiter import Limiter
limiter = Limiter(app, default_limits=["100/hour"])
```

### 📱 Mobile App
Your Python API endpoints (`/api/weather`, `/api/forecast`) are already
REST API endpoints — a React Native or Flutter mobile app can call them.
Just add flask-cors: `pip install flask-cors`

### 📧 Weather Alerts
Use the `schedule` library to check weather every hour and email users
if severe weather is detected.

### 🌡 Unit Toggle (°C / °F)
Pass `units=metric` or `units=imperial` as a URL parameter to the backend.

### 🗄 User Accounts + Saved Cities
Add SQLite with `flask-sqlalchemy`:
```bash
pip install flask-sqlalchemy flask-login
```

---

## 🐛 Troubleshooting

| Problem | Solution |
|---------|----------|
| "Invalid API key" | Wait 10 min after signing up. Check .env has no spaces. |
| "City not found" | Try a different spelling, or add country e.g. "London, UK" |
| Port already in use | Change PORT in .env to 5001 |
| `ModuleNotFoundError` | Run `pip install -r requirements.txt` again |
| App works locally but not on Render | Check Render's "Logs" tab for the error message |
| `venv` not activated | Run `source venv/bin/activate` again |

---

## 📊 API Endpoints Reference

| Endpoint | Method | Params | Returns |
|----------|--------|--------|---------|
| `/` | GET | none | HTML page |
| `/api/weather` | GET | `?city=Mumbai` | Current weather JSON |
| `/api/weather/coords` | GET | `?lat=19.07&lon=72.87` | Current weather by GPS |
| `/api/forecast` | GET | `?city=Mumbai` | 5-day forecast JSON |

---

## 🛡 Security Checklist

- ✅ API key stored in `.env`, never in code
- ✅ `.env` in `.gitignore` (never committed to GitHub)
- ✅ `DEBUG=False` in production
- ✅ `SECRET_KEY` set to a random string in production
- ⬜ Add rate limiting before going viral (flask-limiter)
- ⬜ Add HTTPS (Render provides this automatically)