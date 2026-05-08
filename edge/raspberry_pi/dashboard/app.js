let previousRisk = null;
let audioUnlocked = false;

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
  if (el) {
    el.textContent = value;
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
  if (probability === null || probability === undefined) {
    return { text: "UNKNOWN", className: "medium", percent: 50 };
  }

  const percent = Math.min(100, Math.max(0, probability * 100));

  if (probability >= 0.7) {
    return { text: "HIGH", className: "high", percent };
  }

  if (probability >= 0.4) {
    return { text: "MEDIUM", className: "medium", percent };
  }

  return { text: "LOW", className: "low", percent };
}


function formatTime(timestamp) {
  if (!timestamp) return "--";

  return new Date(timestamp).toLocaleTimeString([], {
    hour: "numeric",
    minute: "2-digit",
    second: "2-digit"
  });
}


function updateNightMode() {
  const hour = new Date().getHours();

  if (hour >= 20 || hour < 6) {
    document.body.classList.add("night-mode");
  } else {
    document.body.classList.remove("night-mode");
  }
}


function updateRiskStyling(risk) {
  const speedSign = document.getElementById("speed-shell");
  const alertBanner = document.getElementById("alert-banner");

  speedSign.classList.remove(
    "low-border",
    "medium-border",
    "high-border",
    "high-pulse"
  );

  if (risk.text === "LOW") {
    document.body.classList.remove("high-risk-mode");
    speedSign.classList.add("low-border");
    alertBanner.classList.add("hidden");
    alertBanner.classList.remove("blink");
  } else if (risk.text === "MEDIUM") {
    document.body.classList.remove("high-risk-mode");
    speedSign.classList.add("medium-border");
    alertBanner.classList.add("hidden");
    alertBanner.classList.remove("blink");
  } else if (risk.text === "HIGH") {
    document.body.classList.add("high-risk-mode");
    speedSign.classList.add("high-border", "high-pulse");
    alertBanner.classList.remove("hidden");
    alertBanner.classList.add("blink");

    if (previousRisk !== "HIGH") {
      triggerHighRiskAlert();
    }
  }

  previousRisk = risk.text;
}


function summarizeSensors(data) {
  const gpsStatus = data.gps?.fix_valid ? "GPS OK" : "GPS MISSING";

  let motionStatus = "Motion Normal";

  if (data.imu?.hard_brake) {
    motionStatus = "Hard Braking";
  } else if (data.imu?.sharp_turn) {
    motionStatus = "Sharp Turn";
  }

  return `${gpsStatus} / ${motionStatus}`;
}


async function fetchSensors() {
  try {
    const response = await fetch("/api/sensors", { cache: "no-store" });

    if (!response.ok) {
      throw new Error("No sensor data");
    }

    const data = await response.json();
    setText("sensor-summary", summarizeSensors(data));
  } catch (error) {
    setText("sensor-summary", "GPS Missing / Motion Unknown");
  }
}


async function updateDashboard() {
  updateNightMode();

  try {
    const response = await fetch("/api/latest", { cache: "no-store" });

    if (!response.ok) {
      throw new Error("No latest prediction available");
    }

    const data = await response.json();

    const probability = data.future_congestion_probability;
    const risk = getRisk(probability);

    updateRiskStyling(risk);

    const speedEl = document.getElementById("speed");
    const newSpeed = data.recommended_speed_mph ?? "--";

    if (speedEl && speedEl.textContent !== String(newSpeed)) {
      speedEl.classList.add("speed-change");
      setTimeout(() => speedEl.classList.remove("speed-change"), 250);
    }

    setText("speed", newSpeed);

    const riskEl = document.getElementById("risk");
    if (riskEl) {
      riskEl.textContent = risk.text;
      riskEl.className = `risk-value ${risk.className}`;
    }

    const riskFill = document.getElementById("risk-fill");
    if (riskFill) {
      riskFill.style.width = `${risk.percent}%`;
    }

    setText(
      "probability",
      probability !== null && probability !== undefined
        ? probability.toFixed(3)
        : "--"
    );

    setText(
      "current-speed",
      data.speed_mph !== null && data.speed_mph !== undefined
        ? `${Math.round(data.speed_mph)} MPH`
        : "--"
    );

    setText(
      "speed-limit",
      data.speed_limit_mph !== null && data.speed_limit_mph !== undefined
        ? `${Math.round(data.speed_limit_mph)} MPH`
        : "--"
    );

    setText("mode", data.mode ?? "--");
    setText("updated", formatTime(data.timestamp));

    const connection = document.getElementById("connection");
    if (connection) {
      connection.textContent = "Connected";
      connection.className = "connected";
    }
  } catch (error) {
    const connection = document.getElementById("connection");
    if (connection) {
      connection.textContent = "Disconnected";
      connection.className = "disconnected";
    }
  }
}


updateDashboard();
fetchSensors();

setInterval(() => {
  updateDashboard();
  fetchSensors();
}, 3000);