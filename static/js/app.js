// ============================================================
// static/js/app.js
// ============================================================

// â”€â”€ DOM References â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
const cityInput       = document.getElementById("cityInput");
const searchBtn       = document.getElementById("searchBtn");
const locationBtn     = document.getElementById("locationBtn");
const locationCta     = document.getElementById("locationCta");
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
const feedbackModal   = document.getElementById("feedbackModal");
const feedbackClose   = document.getElementById("feedbackClose");
const feedbackForm    = document.getElementById("feedbackForm");
const feedbackNext    = document.getElementById("feedbackNext");
const feedbackBack    = document.getElementById("feedbackBack");
const feedbackStatus  = document.getElementById("feedbackStatus");
const feedbackSteps   = document.querySelectorAll(".feedback-step");
const ratingInputs    = document.querySelectorAll('input[name="rating"]');
const FEEDBACK_SHOWN_KEY = "nimbus-feedback-shown";
const LOCATION_CTA_CLICKED_KEY = "nimbus-location-cta-clicked";
const FEEDBACK_PROMPT_DELAY_MS = 2000;
let feedbackPromptTimer = null;
const ICON_BASE_URL = "https://openweathermap.org/img/wn/";
const iconUrlCache = new Map();

initRuntimePerformanceMode();
primeStaticAssets();

function initRuntimePerformanceMode() {
  const root = document.documentElement;
  const connection = navigator.connection || navigator.mozConnection || navigator.webkitConnection;

  const reducedMotion =
    typeof window.matchMedia === "function" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  const cores = Number(navigator.hardwareConcurrency || 0);
  const memory = Number(navigator.deviceMemory || 0);

  const lowCores = cores > 0 && cores <= 4;
  const lowMemory = memory > 0 && memory <= 4;
  const saveData = Boolean(connection && connection.saveData);
  const slowConnection = Boolean(connection && String(connection.effectiveType || "").includes("2g"));

  if (reducedMotion) {
    root.classList.add("reduce-motion");
  }

  if (reducedMotion || lowCores || lowMemory || saveData || slowConnection) {
    root.classList.add("perf-lite");
  }
}

function primeStaticAssets() {
  if (!weatherIcon) return;
  weatherIcon.decoding = "async";
  weatherIcon.loading = "eager";
  weatherIcon.setAttribute("fetchpriority", "high");
}

function getWeatherIconUrl(iconCode) {
  const code = String(iconCode || "").trim();
  if (!code) return "";
  if (!iconUrlCache.has(code)) {
    iconUrlCache.set(code, `${ICON_BASE_URL}${code}@2x.png`);
  }
  return iconUrlCache.get(code);
}


// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
//  VISITOR TRACKING
//  Runs on page load. Collects everything the browser exposes
//  about the visitor and sends it to our Python backend.
//  Location coords are only collected if the user clicks
//  "Use My Location" and grants permission.
// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

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
      // â”€â”€ Browser & Device â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
      user_agent:        navigator.userAgent,
      // Full browser string e.g.
      // "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/125..."

      browser_language:  navigator.language || navigator.userLanguage,
      // e.g. "en-US", "hi-IN", "fr-FR"

      languages:         (navigator.languages || []).join(", "),
      // All accepted languages e.g. "en-US, en, hi"

      platform:          navigator.platform,
      // e.g. "Win32", "MacIntel", "Linux x86_64"

      // â”€â”€ Screen â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
      screen_width:      screen.width,
      screen_height:     screen.height,
      // Physical screen resolution e.g. 1920 x 1080

      viewport_width:    window.innerWidth,
      viewport_height:   window.innerHeight,
      // Browser window size (smaller than screen if windowed)

      color_depth:       screen.colorDepth,
      // Bits per pixel â€” 24 or 32 for modern displays

      pixel_ratio:       window.devicePixelRatio,
      // 1 = normal, 2 = retina/HiDPI display

      // â”€â”€ Time & Location â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
      timezone:          Intl.DateTimeFormat().resolvedOptions().timeZone,
      // e.g. "Asia/Kolkata", "America/New_York"

      timezone_offset:   new Date().getTimezoneOffset(),
      // Minutes offset from UTC. India = -330 (UTC+5:30)

      local_time:        new Date().toISOString(),
      // e.g. "2025-07-15T14:32:01.000Z"

      // â”€â”€ Page info â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
      page_url:          window.location.href,
      referrer:          document.referrer || "direct",
      // referrer = the URL they came from. Empty = typed directly.

      // â”€â”€ Connection â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
      // navigator.connection is not available in all browsers
      connection_type:   navigator.connection?.effectiveType || "unknown",
      // e.g. "4g", "3g", "2g", "slow-2g"

      // â”€â”€ Touch support â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
      is_touch_device:   ("ontouchstart" in window) || navigator.maxTouchPoints > 0,
      // true = phone/tablet, false = desktop

      // â”€â”€ Cookies & Storage â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
      cookies_enabled:   navigator.cookieEnabled,

      // â”€â”€ Location (GPS) â€” only if extras provides it â”€â”€â”€â”€â”€â”€â”€â”€
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
      // JSON.stringify converts JavaScript object â†’ JSON string
    });

    // We don't await a response or show anything to the user.
    // Tracking is completely silent in the background.

  } catch (err) {
    // If tracking fails, silently ignore â€” never break the main app
    console.debug("Tracking skipped:", err.message);
  }
}

// â”€â”€ Fire tracking on page load â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
// Runs immediately when the page opens, before the user does anything.
// Uses requestIdleCallback so it runs when browser is idle (not busy rendering).
// Falls back to setTimeout if requestIdleCallback isn't supported.
if (typeof requestIdleCallback !== "undefined") {
  requestIdleCallback(() => trackVisitor());
} else {
  setTimeout(() => trackVisitor(), 500);
}


// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
//  EVENT LISTENERS
// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

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
    // â”€â”€ SUCCESS: user allowed location â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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

    // â”€â”€ ERROR: user denied or location unavailable â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    (err) => {
      hideLoading();
      // Track that location was denied (useful analytics)
      trackVisitor({ location_granted: false, location_error: err.message });
      showError("Location access denied. Please search manually.");
    },

    // â”€â”€ Options â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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

setupFeedbackHandlers();
setupLocationCtaNudge();


// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
//  CORE FUNCTIONS
// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

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
    maybeShowFeedbackPrompt();

  } catch (err) {
    showError("Could not connect to the server. Check your connection.");
    console.error("Network error:", err);
  } finally {
    hideLoading();
  }
}


/**
 * BUG FIX: Previously this did Promise.all with an empty-city forecast
 * call at the same time as the coords call â€” the empty city failed
 * validation and crashed everything.
 *
 * FIX: Fetch weather by coords FIRST. Once we have the city name
 * from that response, THEN fetch the forecast using the real city name.
 * Sequential, not parallel â€” correct order guaranteed.
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
    maybeShowFeedbackPrompt();

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


// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
//  RENDER FUNCTIONS
// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

function renderWeather(data) {
  cityName.textContent     = data.city;
  countryBadge.textContent = data.country;
  currentTemp.textContent  = data.temp;
  feelsLike.textContent    = `Feels like ${data.feels_like}Â°`;
  tempRange.textContent    = `H:${data.temp_max}Â° Â· L:${data.temp_min}Â°`;
  weatherDesc.textContent  = data.description;

  const heroIconUrl = getWeatherIconUrl(data.icon);
  if (heroIconUrl) {
    if (weatherIcon.src !== heroIconUrl) {
      weatherIcon.src = heroIconUrl;
    }
  } else {
    weatherIcon.removeAttribute("src");
  }
  weatherIcon.alt = data.description || "weather icon";

  humidityEl.textContent   = `${data.humidity}%`;
  windSpeedEl.textContent  = `${data.wind_speed} m/s`;
  windDirEl.textContent    = degreesToCompass(data.wind_deg);
  visibilityEl.textContent = data.visibility > 0 ? `${data.visibility} km` : "N/A";
  pressureEl.textContent   = `${data.pressure} hPa`;

  if (typeof requestAnimationFrame !== "undefined") {
    requestAnimationFrame(() => {
      humidityBar.style.width = `${data.humidity}%`;
    });
  } else {
    humidityBar.style.width = `${data.humidity}%`;
  }

  sunriseEl.textContent = formatTime(data.sunrise, data.timezone);
  sunsetEl.textContent  = formatTime(data.sunset, data.timezone);
  positionSunOnArc(data.sunrise, data.sunset, data.timezone);
  applyTemperatureTheme(data.temp);
}


function renderForecast(data) {
  if (!data.forecast || data.error) return;
  forecastGrid.textContent = "";

  const days = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
  const fragment = document.createDocumentFragment();

  data.forecast.forEach((day, index) => {
    const date    = new Date(day.date + "T12:00:00");
    const dayName = index === 0 ? "Today" : days[date.getDay()];
    const item = document.createElement("div");
    item.className = "forecast-item";

    const dayLabel = document.createElement("div");
    dayLabel.className = "forecast-day";
    dayLabel.textContent = dayName;

    const icon = document.createElement("img");
    icon.className = "forecast-icon";
    icon.src = getWeatherIconUrl(day.icon);
    icon.alt = day.description || "forecast icon";
    icon.loading = index < 2 ? "eager" : "lazy";
    icon.decoding = "async";
    icon.width = 44;
    icon.height = 44;

    const maxTemp = document.createElement("div");
    maxTemp.className = "forecast-temp-max";
    maxTemp.textContent = `${day.temp_max}\u00B0`;

    const minTemp = document.createElement("div");
    minTemp.className = "forecast-temp-min";
    minTemp.textContent = `${day.temp_min}\u00B0`;

    item.append(dayLabel, icon, maxTemp, minTemp);
    fragment.appendChild(item);
  });

  forecastGrid.appendChild(fragment);
}


// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
//  UTILITY FUNCTIONS
// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

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

// â”€â”€ UI State Helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

function setupLocationCtaNudge() {
  if (!locationBtn || !locationCta) return;
  const perfLiteMode = document.documentElement.classList.contains("perf-lite");

  if (!hasUsedLocationCta() && !perfLiteMode) {
    locationCta.classList.add("location-cta-nudge");
  }

  locationBtn.addEventListener("click", () => {
    locationCta.classList.remove("location-cta-nudge");
    markLocationCtaUsed();
  });
}

function hasUsedLocationCta() {
  try {
    return localStorage.getItem(LOCATION_CTA_CLICKED_KEY) === "true";
  } catch (_) {
    return false;
  }
}

function markLocationCtaUsed() {
  try {
    localStorage.setItem(LOCATION_CTA_CLICKED_KEY, "true");
  } catch (_) {
    // Ignore storage limitations and keep UI functional.
  }
}

function setupFeedbackHandlers() {
  if (!feedbackModal || !feedbackForm || !feedbackClose) return;

  feedbackClose.addEventListener("click", closeFeedbackModal);

  feedbackModal.addEventListener("click", (event) => {
    if (event.target === feedbackModal) {
      closeFeedbackModal();
    }
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !feedbackModal.classList.contains("hidden")) {
      closeFeedbackModal();
    }
  });

  ratingInputs.forEach((input) => {
    input.addEventListener("change", () => {
      if (feedbackNext) feedbackNext.disabled = false;
    });
  });

  if (feedbackNext) {
    feedbackNext.addEventListener("click", () => setFeedbackStep(2));
  }

  if (feedbackBack) {
    feedbackBack.addEventListener("click", () => setFeedbackStep(1));
  }

  feedbackForm.addEventListener("submit", handleFeedbackSubmit);
}

function maybeShowFeedbackPrompt() {
  if (!feedbackModal || !feedbackForm) return;
  if (hasSeenFeedbackPrompt() || feedbackPromptTimer) return;

  feedbackPromptTimer = window.setTimeout(() => {
    feedbackPromptTimer = null;
    if (hasSeenFeedbackPrompt()) return;

    markFeedbackPromptSeen();
    openFeedbackModal();
  }, FEEDBACK_PROMPT_DELAY_MS);
}

function hasSeenFeedbackPrompt() {
  try {
    return localStorage.getItem(FEEDBACK_SHOWN_KEY) === "true";
  } catch (_) {
    return false;
  }
}

function markFeedbackPromptSeen() {
  try {
    localStorage.setItem(FEEDBACK_SHOWN_KEY, "true");
  } catch (_) {
    // Ignore storage limitations and keep UI functional.
  }
}

function openFeedbackModal() {
  resetFeedbackForm();
  feedbackModal.classList.remove("hidden");
  document.body.classList.add("feedback-open");
}

function closeFeedbackModal() {
  feedbackModal.classList.add("hidden");
  document.body.classList.remove("feedback-open");
}

function setFeedbackStep(stepNumber) {
  feedbackSteps.forEach((step) => {
    const isCurrentStep = Number(step.dataset.step) === stepNumber;
    step.classList.toggle("hidden", !isCurrentStep);
  });
}

function resetFeedbackForm() {
  feedbackForm.reset();
  setFeedbackStep(1);
  if (feedbackNext) feedbackNext.disabled = true;
  if (feedbackStatus) feedbackStatus.textContent = "";
}

async function handleFeedbackSubmit(event) {
  event.preventDefault();

  const formData = new FormData(feedbackForm);
  const payload = {
    rating: Number(formData.get("rating")),
    location_experience: formData.get("locationExperience"),
    submitted_at: new Date().toISOString(),
  };

  console.log("Nimbus feedback submitted:", payload);

  if (feedbackStatus) {
    feedbackStatus.textContent = "Thanks for the feedback!";
  }

  await Promise.resolve();

  setTimeout(() => {
    closeFeedbackModal();
    resetFeedbackForm();
  }, 900);
}

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

