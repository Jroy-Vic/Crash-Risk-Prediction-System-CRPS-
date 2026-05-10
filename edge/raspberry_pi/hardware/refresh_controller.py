def choose_poll_interval(sensor_data, default_interval=30):
    if not sensor_data:
        return 30

    imu = sensor_data.get("imu", {})

    if imu.get("hard_brake"):
        return 1

    if imu.get("sharp_turn"):
        return 2

    return default_interval