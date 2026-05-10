let latestGps = { fix_valid: false };
let latestImu = {
  hard_brake: false,
  sharp_turn: false,
  accel_x: 0,
  accel_y: 0,
  accel_z: 0
};

async function requestMotionPermissionIfNeeded() {
  if (
    typeof DeviceMotionEvent !== "undefined" &&
    typeof DeviceMotionEvent.requestPermission === "function"
  ) {
    try {
      const permission = await DeviceMotionEvent.requestPermission();
      return permission === "granted";
    } catch {
      return false;
    }
  }

  return true;
}

function startGpsTracking() {
  if (!("geolocation" in navigator)) {
    latestGps = { fix_valid: false, error: "geolocation_not_supported" };
    return;
  }

  navigator.geolocation.watchPosition(
    (position) => {
      latestGps = {
        fix_valid: true,
        latitude: position.coords.latitude,
        longitude: position.coords.longitude,
        accuracy_m: position.coords.accuracy,
        speed_mph:
          position.coords.speed !== null
            ? position.coords.speed * 2.23694
            : null,
        heading_deg: position.coords.heading ?? null,
        timestamp: new Date().toISOString()
      };
    },
    (error) => {
      latestGps = {
        fix_valid: false,
        error: error.message,
        timestamp: new Date().toISOString()
      };
    },
    {
      enableHighAccuracy: true,
      maximumAge: 1000,
      timeout: 7000
    }
  );
}

function startImuTracking() {
  window.addEventListener("devicemotion", (event) => {
    const ax = event.accelerationIncludingGravity?.x ?? 0;
    const ay = event.accelerationIncludingGravity?.y ?? 0;
    const az = event.accelerationIncludingGravity?.z ?? 0;

    latestImu = {
      accel_x: ax,
      accel_y: ay,
      accel_z: az,

      hard_brake: Math.abs(ay) > 5.5,
      sharp_turn: Math.abs(ax) > 4.5,

      timestamp: new Date().toISOString()
    };
  });
}

function uploadPhoneSensors() {
  fetch("/api/sensors/update", {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      timestamp: new Date().toISOString(),
      source: "phone",
      gps: latestGps,
      imu: latestImu
    })
  }).catch(() => {});
}

async function startPhoneSensors() {
  startGpsTracking();

  const motionAllowed = await requestMotionPermissionIfNeeded();

  if (motionAllowed) {
    startImuTracking();
  }

  setInterval(uploadPhoneSensors, 1000);
}

document.addEventListener(
  "click",
  () => {
    startPhoneSensors();
  },
  { once: true }
);