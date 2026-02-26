// ============================================================
// static/js/app.js
// ============================================================
// This is the "brain" of the frontend. It:
//   1. Listens for user actions (typing, clicking)
//   2. Calls our Python/Flask API to get weather data
//   3. Updates the HTML page with the results
//
// No external libraries needed — pure vanilla JavaScript.
// ============================================================


// ── DOM References ────────────────────────────────────────────
// We grab all the HTML elements we'll need to read or update.
// Storing them in variables is faster than calling getElementById() each time.
const cityInput       = document.getElementById("cityInput");
const searchBtn       = document.getElementById("searchBtn");
const locationBtn     = document.getElementById("locationBtn");
const errorMsg        = document.getElementById("errorMsg");
const errorText       = document.getElementById("errorText");
const loadingSpinner  = document.getElementById("loadingSpinner");
const weatherResults  = document.getElementById("weatherResults");
const emptyState      = document.getElementById("emptyState");

// Hero card elements
const cityName        = document.getElementById("cityName");
const countryBadge    = document.getElementById("countryBadge");
const currentTemp     = document.getElementById("currentTemp");
const feelsLike       = document.getElementById("feelsLike");
const tempRange       = document.getElementById("tempRange");
const weatherIcon     = document.getElementById("weatherIcon");
const weatherDesc     = document.getElementById("weatherDesc");

// Stat card elements
const humidityEl      = document.getElementById("humidity");
const humidityBar     = document.getElementById("humidityBar");
const windSpeedEl     = document.getElementById("windSpeed");
const windDirEl       = document.getElementById("windDir");
const visibilityEl    = document.getElementById("visibility");
const pressureEl      = document.getElementById("pressure");

// Sun card elements
const sunriseEl       = document.getElementById("sunrise");
const sunsetEl        = document.getElementById("sunset");
const sunPosition     = document.getElementById("sunPosition");

// Forecast
const forecastGrid    = document.getElementById("forecastGrid");

// City quick-chips
const cityChips       = document.querySelectorAll(".city-chip");
// querySelectorAll returns a NodeList of ALL elements matching the selector


// ══════════════════════════════════════════════════════════════
//  EVENT LISTENERS
//  These tell the browser: "when X happens, run Y function"
// ══════════════════════════════════════════════════════════════

// Search button click
searchBtn.addEventListener("click", () => {
  const city = cityInput.value.trim();  // .trim() removes leading/trailing spaces
  if (city) searchCity(city);
});

// Press Enter key in the input field
cityInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    const city = cityInput.value.trim();
    if (city) searchCity(city);
  }
});

// "Use My Location" button
locationBtn.addEventListener("click", () => {
  // navigator.geolocation is a browser API for getting GPS coordinates
  if (!navigator.geolocation) {
    showError("Geolocation is not supported by your browser.");
    return;
  }

  showLoading();

  navigator.geolocation.getCurrentPosition(
    // Success callback — runs when user allows location access
    (position) => {
      const { latitude, longitude } = position.coords;
      // Destructuring: pulls latitude and longitude out of position.coords
      fetchWeatherByCoords(latitude, longitude);
    },
    // Error callback — runs when user denies or location fails
    (error) => {
      hideLoading();
      showError("Location access denied. Please search manually.");
    }
  );
});

// City quick-chips
cityChips.forEach((chip) => {
  // forEach loops over each chip button and attaches a click listener
  chip.addEventListener("click", () => {
    const city = chip.dataset.city;
    // dataset.city reads the data-city="Mumbai" attribute from the HTML
    cityInput.value = city;
    searchCity(city);
  });
});


// ══════════════════════════════════════════════════════════════
//  CORE FUNCTIONS
// ══════════════════════════════════════════════════════════════

/**
 * Main search function. Called when user submits a city name.
 * Fetches both current weather AND forecast in parallel.
 *
 * @param {string} city - the city name to search
 */
async function searchCity(city) {
  // async functions can use 'await' to pause and wait for API responses
  showLoading();
  hideError();

  try {
    // Promise.all runs BOTH fetches at the same time (parallel, not sequential)
    // This is faster than doing them one after the other.
    const [weatherData, forecastData] = await Promise.all([
      fetchJSON(`/api/weather?city=${encodeURIComponent(city)}`),
      fetchJSON(`/api/forecast?city=${encodeURIComponent(city)}`),
    ]);
    // encodeURIComponent("New York") → "New%20York" (safe for URLs)

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
    // console.error logs to browser DevTools (F12) — useful for debugging
  } finally {
    hideLoading();
    // finally block ALWAYS runs, whether try succeeded or catch ran.
    // Perfect for hiding the loading spinner no matter what.
  }
}


/**
 * Fetches weather using browser GPS coordinates.
 * @param {number} lat - latitude
 * @param {number} lon - longitude
 */
async function fetchWeatherByCoords(lat, lon) {
  try {
    const [weatherData, forecastData] = await Promise.all([
      fetchJSON(`/api/weather/coords?lat=${lat}&lon=${lon}`),
      fetchJSON(`/api/forecast?city=${encodeURIComponent("")}`),
      // For forecast, we'll fetch by name after we get the city from coords
    ]);

    if (weatherData.error) {
      showError(weatherData.error);
      return;
    }

    // Once we have the city name from coordinates, fetch forecast for that city
    const forecastByName = await fetchJSON(`/api/forecast?city=${encodeURIComponent(weatherData.city)}`);

    renderWeather(weatherData);
    renderForecast(forecastByName);
    showResults();

    // Also fill in the search box with the detected city name
    cityInput.value = weatherData.city;

  } catch (err) {
    showError("Failed to fetch weather for your location.");
  } finally {
    hideLoading();
  }
}


/**
 * Generic JSON fetcher. Makes a GET request and returns parsed JSON.
 * All our API calls go through this single function.
 *
 * @param {string} url - the API endpoint URL
 * @returns {Promise<object>} - the parsed JSON response
 */
async function fetchJSON(url) {
  const response = await fetch(url);
  // fetch() is the browser's built-in HTTP request function
  // await pauses here until the server responds

  if (!response.ok) {
    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    // throw stops execution and jumps to the nearest catch block
  }

  return response.json();
  // .json() parses the response body as JSON → gives us a JavaScript object
}


// ══════════════════════════════════════════════════════════════
//  RENDER FUNCTIONS
//  These take data from the API and put it into the HTML.
// ══════════════════════════════════════════════════════════════

/**
 * Updates the main weather display with fetched data.
 * @param {object} data - weather data from /api/weather
 */
function renderWeather(data) {
  // ── Hero card ──────────────────────────────────────────────
  cityName.textContent     = data.city;
  countryBadge.textContent = data.country;
  currentTemp.textContent  = data.temp;
  feelsLike.textContent    = `Feels like ${data.feels_like}°`;
  tempRange.textContent    = `H:${data.temp_max}° · L:${data.temp_min}°`;
  weatherDesc.textContent  = data.description;

  // OpenWeatherMap icon URL format:
  // https://openweathermap.org/img/wn/{icon}@2x.png
  // @2x = high-resolution (2× pixels, crisp on retina screens)
  weatherIcon.src = `https://openweathermap.org/img/wn/${data.icon}@2x.png`;
  weatherIcon.alt = data.description;

  // ── Stat cards ─────────────────────────────────────────────
  humidityEl.textContent  = `${data.humidity}%`;
  windSpeedEl.textContent = `${data.wind_speed} m/s`;
  windDirEl.textContent   = degreesToCompass(data.wind_deg);
  // e.g. 270 degrees → "W" (West)

  visibilityEl.textContent = data.visibility > 0 ? `${data.visibility} km` : "N/A";
  pressureEl.textContent   = `${data.pressure} hPa`;

  // Animate humidity bar: set width AFTER a tiny delay so the animation plays
  setTimeout(() => {
    humidityBar.style.width = `${data.humidity}%`;
  }, 300);

  // ── Sunrise / Sunset ───────────────────────────────────────
  sunriseEl.textContent = formatTime(data.sunrise, data.timezone);
  sunsetEl.textContent  = formatTime(data.sunset, data.timezone);

  // Position the sun icon on the arc based on current time
  positionSunOnArc(data.sunrise, data.sunset, data.timezone);

  // ── Dynamic background ─────────────────────────────────────
  // Subtly shift the background color based on temperature
  applyTemperatureTheme(data.temp);
}


/**
 * Renders the 5-day forecast grid.
 * @param {object} data - forecast data from /api/forecast
 */
function renderForecast(data) {
  if (!data.forecast || data.error) return;

  // Clear existing forecast items (in case user searches a new city)
  forecastGrid.innerHTML = "";

  const days = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
  // Days of the week array — we index into this with .getDay()

  data.forecast.forEach((day, index) => {
    // Create a date object from the date string "2025-07-15"
    const date    = new Date(day.date + "T12:00:00");
    // T12:00:00 = noon — prevents timezone edge cases where the date shifts
    const dayName = index === 0 ? "Today" : days[date.getDay()];

    // Build the HTML for each forecast item
    const item = document.createElement("div");
    item.className = "forecast-item";

    // Template literal (backtick string) lets us embed JS expressions with ${}
    item.innerHTML = `
      <div class="forecast-day">${dayName}</div>
      <img class="forecast-icon" 
           src="https://openweathermap.org/img/wn/${day.icon}@2x.png" 
           alt="${day.description}" />
      <div class="forecast-temp-max">${day.temp_max}°</div>
      <div class="forecast-temp-min">${day.temp_min}°</div>
    `;

    forecastGrid.appendChild(item);
    // appendChild adds the newly created div into the forecastGrid container
  });
}


// ══════════════════════════════════════════════════════════════
//  UTILITY FUNCTIONS
//  Small helpers used by the render functions above.
// ══════════════════════════════════════════════════════════════

/**
 * Converts wind direction in degrees to a compass label.
 * @param {number} deg - degrees (0-360)
 * @returns {string} - e.g. "NW", "SSE"
 */
function degreesToCompass(deg) {
  const dirs = ["N","NNE","NE","ENE","E","ESE","SE","SSE","S","SSW","SW","WSW","W","WNW","NW","NNW"];
  // 360 degrees / 16 directions = 22.5 degrees per segment
  const index = Math.round(deg / 22.5) % 16;
  return dirs[index];
}


/**
 * Converts a Unix timestamp + timezone offset to a readable local time.
 * @param {number} unixTime  - seconds since Jan 1, 1970 UTC
 * @param {number} tzOffset  - seconds offset from UTC (e.g. 19800 = +5:30 for India)
 * @returns {string} - e.g. "6:32 AM"
 */
function formatTime(unixTime, tzOffset) {
  // Convert to milliseconds (JS Date uses ms, Unix uses seconds)
  const localMs = (unixTime + tzOffset) * 1000;
  const date    = new Date(localMs);

  // toUTCString gives us a string we can extract hours/minutes from
  const hours   = date.getUTCHours();
  const minutes = date.getUTCMinutes().toString().padStart(2, "0");
  // padStart(2, "0") turns "3" into "03" — ensures 2-digit minutes

  const ampm    = hours >= 12 ? "PM" : "AM";
  const h12     = hours % 12 || 12;  // converts 0 → 12 (midnight), 13 → 1, etc.

  return `${h12}:${minutes} ${ampm}`;
}


/**
 * Positions the sun icon on the SVG arc based on current time.
 * Shows how far through the day we currently are.
 *
 * @param {number} sunrise  - Unix timestamp
 * @param {number} sunset   - Unix timestamp
 * @param {number} tzOffset - seconds from UTC
 */
function positionSunOnArc(sunrise, sunset, tzOffset) {
  const nowUtcSeconds = Math.floor(Date.now() / 1000);
  // Date.now() = milliseconds since epoch → divide by 1000 for seconds

  const localNow     = nowUtcSeconds + tzOffset;
  const localSunrise = sunrise + tzOffset;
  const localSunset  = sunset + tzOffset;

  // What fraction of the day has passed? (0 = just sunrise, 1 = just sunset)
  let progress = (localNow - localSunrise) / (localSunset - localSunrise);
  progress = Math.max(0, Math.min(1, progress));
  // Math.max/min clamps the value between 0 and 1

  // The SVG arc goes from x=10 to x=190 (180 units wide)
  // Map progress (0→1) to x position (10→190)
  const svgX = 10 + progress * 180;

  // Parabolic y: at x=100 (middle) the sun is highest (y=5), edges at y=55
  // Equation: y = 55 - 50 * sin(progress * π)
  const svgY = 55 - 50 * Math.sin(progress * Math.PI);

  if (sunPosition) {
    sunPosition.setAttribute("cx", svgX.toFixed(1));
    sunPosition.setAttribute("cy", svgY.toFixed(1));
  }
}


/**
 * Subtly shifts the background color based on temperature.
 * Cold temps → cooler blues. Hot temps → warmer tones.
 * This is the kind of "magic detail" that makes an app feel alive.
 *
 * @param {number} temp - temperature in Celsius
 */
function applyTemperatureTheme(temp) {
  const root = document.documentElement;
  // document.documentElement is the <html> element — where CSS variables live

  if (temp <= 0) {
    root.style.setProperty("--bg-deep", "#050e1f");
    root.style.setProperty("--orb-color-1", "#60b8ff");  // icy blue
  } else if (temp <= 15) {
    root.style.setProperty("--bg-deep", "#070d1a");
    root.style.setProperty("--orb-color-1", "#4fd1c5");  // cool teal
  } else if (temp <= 30) {
    root.style.setProperty("--bg-deep", "#080d1a");
    root.style.setProperty("--orb-color-1", "#4fd1c5");  // default
  } else {
    root.style.setProperty("--bg-deep", "#0d0a14");
    root.style.setProperty("--orb-color-1", "#f6a623");  // warm golden
  }
}


// ══════════════════════════════════════════════════════════════
//  UI STATE HELPERS
//  Small functions to show/hide sections of the page.
// ══════════════════════════════════════════════════════════════

function showLoading() {
  loadingSpinner.classList.remove("hidden");
  weatherResults.classList.add("hidden");
  emptyState.classList.add("hidden");
  errorMsg.classList.add("hidden");
  // classList.add/remove toggles CSS classes without touching other classes
}

function hideLoading() {
  loadingSpinner.classList.add("hidden");
}

function showResults() {
  weatherResults.classList.remove("hidden");
  emptyState.classList.add("hidden");
}

function showError(message) {
  errorText.textContent = message;
  errorMsg.classList.remove("hidden");
  emptyState.classList.add("hidden");
}

function hideError() {
  errorMsg.classList.add("hidden");
}


// ══════════════════════════════════════════════════════════════
//  AUTO-SEARCH (optional convenience)
//  If you want the app to load your city on startup,
//  uncomment one of these lines:
// ══════════════════════════════════════════════════════════════

// searchCity("Mumbai");        // always load Mumbai on startup
// searchCity("London");

// Or detect user location automatically on page load:
// locationBtn.click();