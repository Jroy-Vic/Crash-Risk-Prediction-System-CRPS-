def choose_poll_interval(sensor_data, default_interval=5):
    if not sensor_data:
        return 10

    imu = sensor_data.get("imu", {})

    if imu.get("hard_brake"):
        return 1

    if imu.get("sharp_turn"):
        return 2

    return default_interval