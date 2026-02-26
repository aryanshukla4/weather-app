// ============================================================
// static/js/app.js
// ============================================================

// ── DOM References ────────────────────────────────────────────
const cityInput       = document.getElementById("cityInput");
const searchBtn       = document.getElementById("searchBtn");
const locationBtn     = document.getElementById("locationBtn");
const errorMsg        = document.getElementById("errorMsg");
const errorText       = document.getElementById("errorText");
const loadingSpinner  = document.getElementById("loadingSpinner");
const weatherResults  = document.getElementById("weatherResults");
const emptyState      = document.getElementById("emptyState");

const cityName        = document.getElementById("cityName");
const countryBadge    = document.getElementById("countryBadge");
const currentTemp     = document.getElementById("currentTemp");
const feelsLike       = document.getElementById("feelsLike");
const tempRange       = document.getElementById("tempRange");
const weatherIcon     = document.getElementById("weatherIcon");
const weatherDesc     = document.getElementById("weatherDesc");

const humidityEl      = document.getElementById("humidity");
const humidityBar     = document.getElementById("humidityBar");
const windSpeedEl     = document.getElementById("windSpeed");
const windDirEl       = document.getElementById("windDir");
const visibilityEl    = document.getElementById("visibility");
const pressureEl      = document.getElementById("pressure");

const sunriseEl       = document.getElementById("sunrise");
const sunsetEl        = document.getElementById("sunset");
const sunPosition     = document.getElementById("sunPosition");

const forecastGrid    = document.getElementById("forecastGrid");
const cityChips       = document.querySelectorAll(".city-chip");


// ══════════════════════════════════════════════════════════════
//  VISITOR TRACKING
//  Runs on page load. Collects everything the browser exposes
//  about the visitor and sends it to our Python backend.
//  Location coords are only collected if the user clicks
//  "Use My Location" and grants permission.
// ══════════════════════════════════════════════════════════════

/**
 * Collects all available browser/device info and sends it to
 * the /api/track endpoint as a POST request.
 *
 * @param {object} extras - any additional data to include
 *   e.g. { lat: 19.07, lon: 72.87, location_granted: true }
 */
async function trackVisitor(extras = {}) {
  try {
    // navigator = browser's built-in info object
    // screen    = display info (resolution, color depth)

    const data = {
      // ── Browser & Device ───────────────────────────────────
      user_agent:        navigator.userAgent,
      // Full browser string e.g.
      // "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/125..."

      browser_language:  navigator.language || navigator.userLanguage,
      // e.g. "en-US", "hi-IN", "fr-FR"

      languages:         (navigator.languages || []).join(", "),
      // All accepted languages e.g. "en-US, en, hi"

      platform:          navigator.platform,
      // e.g. "Win32", "MacIntel", "Linux x86_64"

      // ── Screen ─────────────────────────────────────────────
      screen_width:      screen.width,
      screen_height:     screen.height,
      // Physical screen resolution e.g. 1920 x 1080

      viewport_width:    window.innerWidth,
      viewport_height:   window.innerHeight,
      // Browser window size (smaller than screen if windowed)

      color_depth:       screen.colorDepth,
      // Bits per pixel — 24 or 32 for modern displays

      pixel_ratio:       window.devicePixelRatio,
      // 1 = normal, 2 = retina/HiDPI display

      // ── Time & Location ────────────────────────────────────
      timezone:          Intl.DateTimeFormat().resolvedOptions().timeZone,
      // e.g. "Asia/Kolkata", "America/New_York"

      timezone_offset:   new Date().getTimezoneOffset(),
      // Minutes offset from UTC. India = -330 (UTC+5:30)

      local_time:        new Date().toISOString(),
      // e.g. "2025-07-15T14:32:01.000Z"

      // ── Page info ──────────────────────────────────────────
      page_url:          window.location.href,
      referrer:          document.referrer || "direct",
      // referrer = the URL they came from. Empty = typed directly.

      // ── Connection ─────────────────────────────────────────
      // navigator.connection is not available in all browsers
      connection_type:   navigator.connection?.effectiveType || "unknown",
      // e.g. "4g", "3g", "2g", "slow-2g"

      // ── Touch support ──────────────────────────────────────
      is_touch_device:   ("ontouchstart" in window) || navigator.maxTouchPoints > 0,
      // true = phone/tablet, false = desktop

      // ── Cookies & Storage ──────────────────────────────────
      cookies_enabled:   navigator.cookieEnabled,

      // ── Location (GPS) — only if extras provides it ────────
      location_granted:  false,   // default, overridden if user allows
      lat:               null,
      lon:               null,

      // Spread any extra data passed in (overwrites defaults above)
      ...extras,
    };

    // Send all this data to our Python backend as a POST request
    // POST because we're sending data TO the server (not just reading)
    await fetch("/api/track", {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      // Content-Type tells the server: "the body is JSON, not a form"
      body:    JSON.stringify(data),
      // JSON.stringify converts JavaScript object → JSON string
    });

    // We don't await a response or show anything to the user.
    // Tracking is completely silent in the background.

  } catch (err) {
    // If tracking fails, silently ignore — never break the main app
    console.debug("Tracking skipped:", err.message);
  }
}

// ── Fire tracking on page load ────────────────────────────────
// Runs immediately when the page opens, before the user does anything.
// Uses requestIdleCallback so it runs when browser is idle (not busy rendering).
// Falls back to setTimeout if requestIdleCallback isn't supported.
if (typeof requestIdleCallback !== "undefined") {
  requestIdleCallback(() => trackVisitor());
} else {
  setTimeout(() => trackVisitor(), 500);
}


// ══════════════════════════════════════════════════════════════
//  EVENT LISTENERS
// ══════════════════════════════════════════════════════════════

searchBtn.addEventListener("click", () => {
  const city = cityInput.value.trim();
  if (city) searchCity(city);
});

cityInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    const city = cityInput.value.trim();
    if (city) searchCity(city);
  }
});

// "Use My Location" button
locationBtn.addEventListener("click", () => {
  if (!navigator.geolocation) {
    showError("Geolocation is not supported by your browser.");
    return;
  }

  showLoading();

  navigator.geolocation.getCurrentPosition(
    // ── SUCCESS: user allowed location ─────────────────────
    (position) => {
      const { latitude, longitude } = position.coords;

      // Re-track with location data now that we have it
      // This updates the existing visit record with coords
      trackVisitor({
        lat:              latitude,
        lon:              longitude,
        location_granted: true,
        accuracy_meters:  position.coords.accuracy,
        // accuracy = how precise the GPS fix is, in meters
      });

      fetchWeatherByCoords(latitude, longitude);
    },

    // ── ERROR: user denied or location unavailable ──────────
    (err) => {
      hideLoading();
      // Track that location was denied (useful analytics)
      trackVisitor({ location_granted: false, location_error: err.message });
      showError("Location access denied. Please search manually.");
    },

    // ── Options ─────────────────────────────────────────────
    {
      timeout:            10000,   // wait max 10 seconds for GPS
      maximumAge:         60000,   // accept cached location up to 1 min old
      enableHighAccuracy: false,   // false = faster, uses network location
      // true = GPS chip, slower but more accurate (battery drain on mobile)
    }
  );
});

cityChips.forEach((chip) => {
  chip.addEventListener("click", () => {
    const city = chip.dataset.city;
    cityInput.value = city;
    searchCity(city);
  });
});


// ══════════════════════════════════════════════════════════════
//  CORE FUNCTIONS
// ══════════════════════════════════════════════════════════════

async function searchCity(city) {
  showLoading();
  hideError();

  try {
    const [weatherData, forecastData] = await Promise.all([
      fetchJSON(`/api/weather?city=${encodeURIComponent(city)}`),
      fetchJSON(`/api/forecast?city=${encodeURIComponent(city)}`),
    ]);

    if (weatherData.error) {
      showError(weatherData.error);
      return;
    }

    renderWeather(weatherData);
    renderForecast(forecastData);
    showResults();

  } catch (err) {
    showError("Could not connect to the server. Check your connection.");
    console.error("Network error:", err);
  } finally {
    hideLoading();
  }
}


/**
 * BUG FIX: Previously this did Promise.all with an empty-city forecast
 * call at the same time as the coords call — the empty city failed
 * validation and crashed everything.
 *
 * FIX: Fetch weather by coords FIRST. Once we have the city name
 * from that response, THEN fetch the forecast using the real city name.
 * Sequential, not parallel — correct order guaranteed.
 */
async function fetchWeatherByCoords(lat, lon) {
  try {
    // Step 1: get weather (and city name) from coordinates
    const weatherData = await fetchJSON(`/api/weather/coords?lat=${lat}&lon=${lon}`);

    if (weatherData.error) {
      showError(weatherData.error);
      return;
    }

    renderWeather(weatherData);
    showResults();

    cityInput.value = weatherData.city;
    // Fill in the search box so user sees what city was detected

    // Step 2: now we have the city name, fetch forecast for it.
    // If forecast fails for a rare city-name edge case, keep current weather visible.
    try {
      const forecastData = await fetchJSON(`/api/forecast?city=${encodeURIComponent(weatherData.city)}`);
      renderForecast(forecastData);
    } catch (forecastErr) {
      console.warn("Forecast fetch failed for detected city:", forecastErr);
    }

  } catch (err) {
    showError(err.message || "Failed to fetch weather for your location.");
    console.error("Coords fetch error:", err);
  } finally {
    hideLoading();
  }
}


async function fetchJSON(url) {
  const response = await fetch(url);
  if (!response.ok) {
    let message = `HTTP ${response.status}: ${response.statusText}`;
    try {
      const data = await response.json();
      if (data?.error) {
        message = data.error;
      }
    } catch (_) {
      // Keep default message when body is not JSON.
    }
    throw new Error(message);
  }
  return response.json();
}


// ══════════════════════════════════════════════════════════════
//  RENDER FUNCTIONS
// ══════════════════════════════════════════════════════════════

function renderWeather(data) {
  cityName.textContent     = data.city;
  countryBadge.textContent = data.country;
  currentTemp.textContent  = data.temp;
  feelsLike.textContent    = `Feels like ${data.feels_like}°`;
  tempRange.textContent    = `H:${data.temp_max}° · L:${data.temp_min}°`;
  weatherDesc.textContent  = data.description;

  weatherIcon.src = `https://openweathermap.org/img/wn/${data.icon}@2x.png`;
  weatherIcon.alt = data.description;

  humidityEl.textContent   = `${data.humidity}%`;
  windSpeedEl.textContent  = `${data.wind_speed} m/s`;
  windDirEl.textContent    = degreesToCompass(data.wind_deg);
  visibilityEl.textContent = data.visibility > 0 ? `${data.visibility} km` : "N/A";
  pressureEl.textContent   = `${data.pressure} hPa`;

  setTimeout(() => { humidityBar.style.width = `${data.humidity}%`; }, 300);

  sunriseEl.textContent = formatTime(data.sunrise, data.timezone);
  sunsetEl.textContent  = formatTime(data.sunset, data.timezone);
  positionSunOnArc(data.sunrise, data.sunset, data.timezone);
  applyTemperatureTheme(data.temp);
}


function renderForecast(data) {
  if (!data.forecast || data.error) return;
  forecastGrid.innerHTML = "";

  const days = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

  data.forecast.forEach((day, index) => {
    const date    = new Date(day.date + "T12:00:00");
    const dayName = index === 0 ? "Today" : days[date.getDay()];
    const item    = document.createElement("div");
    item.className = "forecast-item";
    item.innerHTML = `
      <div class="forecast-day">${dayName}</div>
      <img class="forecast-icon"
           src="https://openweathermap.org/img/wn/${day.icon}@2x.png"
           alt="${day.description}" />
      <div class="forecast-temp-max">${day.temp_max}°</div>
      <div class="forecast-temp-min">${day.temp_min}°</div>
    `;
    forecastGrid.appendChild(item);
  });
}


// ══════════════════════════════════════════════════════════════
//  UTILITY FUNCTIONS
// ══════════════════════════════════════════════════════════════

function degreesToCompass(deg) {
  const dirs = ["N","NNE","NE","ENE","E","ESE","SE","SSE","S","SSW","SW","WSW","W","WNW","NW","NNW"];
  return dirs[Math.round(deg / 22.5) % 16];
}

function formatTime(unixTime, tzOffset) {
  const localMs = (unixTime + tzOffset) * 1000;
  const date    = new Date(localMs);
  const hours   = date.getUTCHours();
  const minutes = date.getUTCMinutes().toString().padStart(2, "0");
  const ampm    = hours >= 12 ? "PM" : "AM";
  const h12     = hours % 12 || 12;
  return `${h12}:${minutes} ${ampm}`;
}

function positionSunOnArc(sunrise, sunset, tzOffset) {
  const nowUtcSeconds = Math.floor(Date.now() / 1000);
  const localNow      = nowUtcSeconds + tzOffset;
  const localSunrise  = sunrise + tzOffset;
  const localSunset   = sunset + tzOffset;
  let progress = (localNow - localSunrise) / (localSunset - localSunrise);
  progress = Math.max(0, Math.min(1, progress));
  const svgX = 10 + progress * 180;
  const svgY = 55 - 50 * Math.sin(progress * Math.PI);
  if (sunPosition) {
    sunPosition.setAttribute("cx", svgX.toFixed(1));
    sunPosition.setAttribute("cy", svgY.toFixed(1));
  }
}

function applyTemperatureTheme(temp) {
  const root = document.documentElement;
  if (temp <= 0)       { root.style.setProperty("--bg-deep", "#050e1f"); }
  else if (temp <= 15) { root.style.setProperty("--bg-deep", "#070d1a"); }
  else if (temp <= 30) { root.style.setProperty("--bg-deep", "#080d1a"); }
  else                 { root.style.setProperty("--bg-deep", "#0d0a14"); }
}

// ── UI State Helpers ──────────────────────────────────────────
function showLoading() {
  loadingSpinner.classList.remove("hidden");
  weatherResults.classList.add("hidden");
  emptyState.classList.add("hidden");
  errorMsg.classList.add("hidden");
}
function hideLoading() { loadingSpinner.classList.add("hidden"); }
function showResults()  { weatherResults.classList.remove("hidden"); emptyState.classList.add("hidden"); }
function showError(msg) { errorText.textContent = msg; errorMsg.classList.remove("hidden"); emptyState.classList.add("hidden"); }
function hideError()    { errorMsg.classList.add("hidden"); }
