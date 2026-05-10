import time
from helpers.client_helpers.config_loader import load_config
from helpers.client_helpers.payload_builder import build_live_payload
from helpers.client_helpers.inference_client import get_prediction
from helpers.client_helpers.prediction_writer import write_latest_prediction
from helpers.client_helpers.logging_client import log_prediction
from edge.raspberry_pi.hardware.sensor_sources import load_sensor_data
from edge.raspberry_pi.hardware.refresh_controller import choose_poll_interval

def main():
    config = load_config()

    while True:
        payload = build_live_payload(config)

        print("LIVE PAYLOAD:")
        print(payload)

        result = get_prediction(config, payload)
        if payload.get("is_simulation"):                # If we are in simulation mode, add a flag to the result so the dashboard can display it accordingly
            result["inference_mode"] = "simulation"

        write_latest_prediction(result)
        log_prediction(payload, result)

        print("RESULT:", result)

        sensor_data = load_sensor_data()
        poll_interval = choose_poll_interval(sensor_data, 30)

        time.sleep(poll_interval)

if __name__ == "__main__":
    main()