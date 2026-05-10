from src.utils.crps_logger import CRPSLogger

logger = CRPSLogger()

def log_prediction(payload, result):
    logger.log_prediction({
        "speed_mph": payload.get("speed_mph"),
        "probability": result.get("future_congestion_probability"),
        "mode": result.get("inference_mode"),
    })