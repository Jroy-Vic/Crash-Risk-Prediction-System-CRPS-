let connectionState = "connected"; // connected | disconnected | loading
let previousRisk = null;
let audioUnlocked = false;
let currentView = "drive";
let autoReturnTimer = null;

const alertAudio = new Audio("/static/alert.mp3");
alertAudio.preload = "auto";
alertAudio.loop = false;

document.addEventListener("click", () => {
  audioUnlocked = true;
  alertAudio.play().then(() => {
    alertAudio.pause();
    alertAudio.currentTime = 0;
  }).catch(() => {});
}, { once: true });


function setText(id, value) {
  const el = document.getElementById(id);
  if (el) el.textContent = value;
}


function setTextAnimated(id, value) {
  const el = document.getElementById(id);
  if (!el) return;

  const newValue = String(value);
  if (el.textContent !== newValue) {
    el.textContent = newValue;
    el.classList.remove("value-updated");
    void el.offsetWidth;
    el.classList.add("value-updated");
  }
}


function triggerHighRiskAlert() {
  if (navigator.vibrate) {
    navigator.vibrate([400, 150, 400, 150, 600]);
  }

  if (audioUnlocked) {
    alertAudio.currentTime = 0;
    alertAudio.play().catch(() => {});
  }
}


function getRisk(probability) {
  if (probability === null || probability === undefined || Number.isNaN(Number(probability))) {
    return { text: "UNKNOWN", className: "medium", percent: 50 };
  }

  const p = Number(probability);
  const percent = Math.min(100, Math.max(0, p * 100));

  if (p >= 0.7) return { text: "HIGH", className: "high", percent };
  if (p >= 0.4) return { text: "MEDIUM", className: "medium", percent };
  return { text: "LOW", className: "low", percent };
}


function riskColor(riskText) {
  if (riskText === "HIGH") return "#ff3434";
  if (riskText === "MEDIUM" || riskText === "UNKNOWN") return "#ffc52e";
  return "#4ee34e";
}


function formatTime(timestamp) {
  if (!timestamp) return "--";

  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) return "--";

  return date.toLocaleTimeString([], {
    hour: "numeric",
    minute: "2-digit",
    second: "2-digit"
  });
}


function formatRouteMode(mode) {
  if (!mode) return "--";

  const map = {
    heading_projection: "Forward Projection",
    route_ahead: "Route Prediction"
  };

  return map[mode] ?? String(mode).replaceAll("_", " ").replace(/\b\w/g, c => c.toUpperCase());
}


function formatInferenceMode(mode) {
  if (!mode) return "--";

  const map = {
    simulation: "Simulation Mode",
    online_backend: "Live Prediction",
    onnx_local: "Offline Mode",
    rule_based: "Rule Fallback",
  };

  return map[mode] ?? String(mode).replaceAll("_", " ").replace(/\b\w/g, c => c.toUpperCase());
}


function getProbability(data) {
  return (
    data.congestion_probability_5min_ahead ??
    data.future_congestion_probability ??
    data.congestion_probability ??
    null
  );
}


function getRecommendedSpeed(data) {
  return (
    data.recommended_speed_mph ??
    data.advisory_speed_mph ??
    data.speed_limit_mph ??
    null
  );
}


function getTrafficSpeed(data) {
  return (
    data.target_traffic?.speed_mph ??
    data.speed_mph ??
    data.current_speed_mph ??
    data.vehicle_speed_mph ??
    null
  );
}


function getSpeedLimit(data) {
  return (
    data.speed_limit_mph ??
    data.speed_limit ??
    data.speed_limit_cap_mph ??
    65
  );
}


function updateRiskStyling(risk) {
  const speedShell = document.getElementById("speed-shell");
  const alertBanner = document.getElementById("alert-banner");

  if (!speedShell || !alertBanner) return;

  speedShell.classList.remove("low-border", "medium-border", "high-border", "high-pulse");
  document.body.classList.remove("high-risk-mode");

  if (risk.text === "LOW") {
    speedShell.classList.add("low-border");
    alertBanner.classList.add("hidden");
  } else if (risk.text === "MEDIUM" || risk.text === "UNKNOWN") {
    speedShell.classList.add("medium-border");
    alertBanner.classList.add("hidden");
  } else {
    document.body.classList.add("high-risk-mode");
    speedShell.classList.add("high-border", "high-pulse");
    alertBanner.classList.remove("hidden");

    if (previousRisk !== "HIGH") triggerHighRiskAlert();
  }

  previousRisk = risk.text;

  const trafficBox = document.querySelector(".drive-current-speed");

  if (trafficBox) {
    if (risk.text === "HIGH") {
      trafficBox.style.visibility = "hidden";
      trafficBox.style.opacity = "0";
    } else {
      trafficBox.style.visibility = "visible";
      trafficBox.style.opacity = "1";
    }
  }
}


function animateDonut(donut, targetPct, color) {
  const startPct = Number(donut.dataset.progress ?? 0);
  const duration = 650;
  const startTime = performance.now();

  function step(now) {
    const elapsed = now - startTime;
    const t = Math.min(1, elapsed / duration);
    const eased = 1 - Math.pow(1 - t, 3);

    const currentPct = startPct + (targetPct - startPct) * eased;

    donut.style.background =
      `conic-gradient(${color} ${currentPct}%, #666 ${currentPct}% 100%)`;

    if (t < 1) {
      requestAnimationFrame(step);
    } else {
      donut.dataset.progress = targetPct;
    }
  }

  requestAnimationFrame(step);
}


function setConnectionState(newState) {
  if (connectionState === newState) return;

  connectionState = newState;

  const conn = document.getElementById("connection");
  const dot = document.getElementById("connection-dot");
  const spinner = document.getElementById("connection-spinner");

  if (!conn || !dot || !spinner) return;

  dot.classList.remove("online", "offline");
  spinner.classList.add("hidden");

  if (newState === "connected") {
    conn.textContent = "Connected";
    conn.className = "connected";
    dot.classList.add("online");
  } else if (newState === "loading") {
    conn.textContent = "Reconnecting";
    conn.className = "disconnected";
    spinner.classList.remove("hidden");
  } else {
    conn.textContent = "Disconnected";
    conn.className = "disconnected";
    dot.classList.add("offline");
  }
}


function animateSlider(el, targetPct) {
  if (!el) return;

  const startPct = Number(el.dataset.progress ?? 0);
  const duration = 650;
  const startTime = performance.now();

  function step(now) {
    const elapsed = now - startTime;
    const t = Math.min(1, elapsed / duration);
    const eased = 1 - Math.pow(1 - t, 3);

    const currentPct = startPct + (targetPct - startPct) * eased;
    el.style.left = `${currentPct}%`;

    if (t < 1) {
      requestAnimationFrame(step);
    } else {
      el.dataset.progress = targetPct;
    }
  }

  requestAnimationFrame(step);
}

function updateRiskGauge(probability, risk) {
  const pct = risk.percent;
  const color = riskColor(risk.text);

  const riskFill = document.getElementById("risk-fill");
  if (riskFill) {
    riskFill.style.width = `${pct}%`;
  }

  const analyticsKnob = document.getElementById("analytics-risk-knob");
  animateSlider(analyticsKnob, pct);

  const riskPointer = document.getElementById("risk-pointer");
  animateSlider(riskPointer, pct);

  const donut = document.getElementById("probability-donut");
  if (
    donut &&
    probability !== null &&
    probability !== undefined &&
    !Number.isNaN(Number(probability))
  ) {
    const donutPct = Math.min(100, Math.max(0, Number(probability) * 100));
    animateDonut(donut, donutPct, color);
  }

  const donutLabel = document.getElementById("probability-label");
  if (donutLabel) {
    donutLabel.style.color = color;
    donutLabel.style.textShadow = `0 0 10px ${color}`;
  }

  const analyticsSpeedCard = document.querySelector(".analytics-speed-card");
  if (analyticsSpeedCard) {
    analyticsSpeedCard.classList.remove("low-state", "medium-state", "high-state");

    if (risk.text === "HIGH") {
      analyticsSpeedCard.classList.add("high-state");
    } else if (risk.text === "MEDIUM" || risk.text === "UNKNOWN") {
      analyticsSpeedCard.classList.add("medium-state");
    } else {
      analyticsSpeedCard.classList.add("low-state");
    }
  }
}


function updateRouteAhead(data) {
  const routeAhead = data.route_ahead ?? data.target_segment ?? null;
  const routeMode = routeAhead?.mode ?? data.route_mode ?? data.mode ?? null;

  if (!routeAhead || routeAhead.distance_ahead_m === undefined) {
    setText("target-distance", "--");
    setText("eta", "--");
    setText("target-mode", formatRouteMode(routeMode));
    return;
  }

  const miles = Number(routeAhead.distance_ahead_m) / 1609.344;

  setText("target-distance", `${miles.toFixed(2)} mi`);
  setText("eta", formatTime(routeAhead.eta_timestamp_utc ?? routeAhead.eta_timestamp));
  setText("target-mode", formatRouteMode(routeMode));
}


function updateWeather(data) {
  const temperature = data.temperature_f ?? data.weather?.temperature_f ?? null;
  const visibility = data.visibility_miles ?? data.weather?.visibility_miles ?? null;
  const isRain = data.is_rain ?? data.weather?.is_rain ?? 0;

  let weatherSummary = "--";

  if (temperature !== null && temperature !== undefined) {
    weatherSummary = `${Math.round(Number(temperature))}°F`;

    if (Number(isRain) === 1 || isRain === true) {
      weatherSummary += " / Rain";
    } else if (visibility !== null && visibility !== undefined && Number(visibility) < 5) {
      weatherSummary += " / Low Vis";
    } else {
      weatherSummary += " / Clear";
    }
  }

  setText("weather-summary", weatherSummary);
}


function updateConfidence(data) {
  const confidence = data.route_ahead?.confidence ?? null;

  setText(
    "confidence",
    confidence !== null && confidence !== undefined
      ? `${Math.round(Number(confidence) * 100)}%`
      : "--"
  );
}


function startAnalyticsInactivityTimer() {
  clearTimeout(autoReturnTimer);

  autoReturnTimer = setTimeout(() => {
    if (currentView === "analytics") toggleMode();
  }, 20000);
}


function resetAnalyticsInactivityTimer() {
  if (currentView === "analytics") startAnalyticsInactivityTimer();
}


function toggleMode() {
  const gear = document.getElementById("gear-icon");

  if (gear) {
    gear.classList.remove("gear-spin");
    void gear.offsetWidth; // reset animation
    gear.classList.add("gear-spin");
  }

  const drive = document.getElementById("drive-mode");
  const analytics = document.getElementById("analytics-mode");
  const btn = document.getElementById("mode-toggle");

  if (!drive || !analytics || !btn) return;

  if (currentView === "drive") {
    drive.classList.add("hidden");
    analytics.classList.remove("hidden");
    btn.textContent = "Drive";
    currentView = "analytics";
    startAnalyticsInactivityTimer();
  } else {
    analytics.classList.add("hidden");
    drive.classList.remove("hidden");
    btn.textContent = "Analytics";
    currentView = "drive";
    clearTimeout(autoReturnTimer);
  }
}


async function fetchSensors() {
  try {
    const res = await fetch("/api/sensors", { cache: "no-store" });
    if (!res.ok) throw new Error("No sensor data");

    const data = await res.json();

    const gps = data.gps?.fix_valid ? "GPS OK" : "GPS MISSING";

    let motion = "Motion Normal";
    if (data.imu?.hard_brake) motion = "Hard Braking";
    else if (data.imu?.sharp_turn) motion = "Sharp Turn";

    const summary = `${gps} / ${motion}`;

    setText("sensor-summary", summary);
    setText("sensor-summary-analytics", summary);
    setText("system-status", summary);
  } catch {
    setText("sensor-summary", "GPS Missing / Motion Unknown");
    setText("sensor-summary-analytics", "GPS -- / Motion --");
    setText("system-status", "GPS -- / Motion --");
  }
}


function updateThemeByTime() {
  const hour = new Date().getHours();
  const isNight = hour >= 19 || hour < 6;

  document.body.classList.toggle("night-mode", isNight);
  document.body.classList.toggle("day-mode", !isNight);
}


function updateAccuracyState(data) {
  const banner = document.getElementById("fallback-banner");

  const reducedAccuracy =
    data.accuracy_state === "reduced" ||
    data.backend_reachable === false ||
    data.inference_mode === "rule_based" ||
    data.inference_mode === "onnx_local";

  document.body.classList.toggle("reduced-accuracy-mode", reducedAccuracy);

  if (banner) {
    banner.classList.toggle("hidden", !reducedAccuracy);
  }
}



async function updateDashboard() {
  try {
    const res = await fetch("/api/latest", {
      cache: "no-store",
      headers: {
        "Cache-Control": "no-cache"
      }
    });

    if (connectionState !== "connected") {
      setConnectionState("connected");
    }

    if (!res.ok) throw new Error("No latest prediction");

    const data = await res.json();

    updateAccuracyState(data);

    const probability = getProbability(data);
    const risk = getRisk(probability);
    const recommendedSpeed = getRecommendedSpeed(data);
    const trafficSpeed = getTrafficSpeed(data);
    const speedLimit = getSpeedLimit(data);

    const routeModeText = formatRouteMode(data.route_mode ?? data.mode ?? data.route_ahead?.mode);
    const inferenceModeText = formatInferenceMode(data.inference_mode ?? data.mode);

    updateRiskStyling(risk);
    updateRiskGauge(probability, risk);
    updateRouteAhead(data);
    updateWeather(data);
    updateConfidence(data);

    setTextAnimated("risk", risk.text);
    setTextAnimated("analytics-risk", risk.text);

    setTextAnimated(
      "probability",
      probability !== null && probability !== undefined
        ? `${(Number(probability) * 100).toFixed(1)}%`
        : "--"
    );

    setText(
      "probability-drive",
      probability !== null && probability !== undefined
        ? Number(probability).toFixed(3)
        : "--"
    );

    setText(
      "probability-label",
      risk.text === "LOW" ? "Very Low" : risk.text
    );

    setTextAnimated(
      "speed",
      recommendedSpeed !== null && recommendedSpeed !== undefined
        ? Math.round(Number(recommendedSpeed))
        : "--"
    );

    setText(
      "speed-analytics",
      recommendedSpeed !== null && recommendedSpeed !== undefined
        ? Math.round(Number(recommendedSpeed))
        : "--"
    );

    const trafficSpeedText =
      trafficSpeed !== null && trafficSpeed !== undefined
        ? `${Math.round(Number(trafficSpeed))} MPH`
        : "--";

    setText("current-speed", trafficSpeedText);
    setText("current-speed-drive", trafficSpeedText);
    setTextAnimated("current-speed-drive-main", trafficSpeedText);

    const speedLimitText =
      speedLimit !== null && speedLimit !== undefined
        ? `${Math.round(Number(speedLimit))} MPH`
        : "--";

   setText("speed-limit", speedLimitText);

    const speedLimitNumber =
      speedLimit !== null && speedLimit !== undefined
        ? Math.round(Number(speedLimit))
        : "--";

    const speedLimitDriveEl = document.getElementById("speed-limit-drive");
    if (speedLimitDriveEl) {
      speedLimitDriveEl.innerHTML =
        speedLimitNumber !== "--"
          ? `<span>${speedLimitNumber}</span><small>MPH</small>`
          : "--";
    }

    setText("mini-speed-limit-value", speedLimitNumber);
    setText("mini-speed-limit-drive", speedLimitNumber);
    setText("mode", inferenceModeText);
    setText("mode-drive", routeModeText);
    setText("updated", formatTime(data.timestamp));

    const conn = document.getElementById("connection");
    if (conn) {
      conn.textContent = "Connected";
      conn.className = "connected";
    }

    const dot = document.getElementById("connection-dot");
    if (dot) dot.className = "connection-dot online";
  }
  
  catch (error) {
    if (connectionState === "connected") {
      setConnectionState("loading");
    } else {
      setConnectionState("disconnected");
    }
    console.error("Dashboard update failed:", error);

    const conn = document.getElementById("connection");
    if (conn) {
      conn.textContent = "Disconnected";
      conn.className = "disconnected";
    }

    const dot = document.getElementById("connection-dot");
    if (dot) dot.className = "connection-dot offline";
  }
}


document.addEventListener("DOMContentLoaded", () => {
  const toggleButton = document.getElementById("mode-toggle");

  if (toggleButton) {
    toggleButton.addEventListener("click", toggleMode);
  }

  ["touchstart", "touchmove", "click", "scroll"].forEach((eventName) => {
    document.addEventListener(eventName, resetAnalyticsInactivityTimer, {
      passive: true
    });
  });

  updateThemeByTime();
  updateDashboard();
  fetchSensors();

  const interval = /Mobi|Android/i.test(navigator.userAgent) ? 2000 : 3000;

  setInterval(() => {
    updateDashboard();
    fetchSensors();
  }, interval);
});