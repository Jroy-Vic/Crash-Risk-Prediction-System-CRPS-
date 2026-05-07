import json
import joblib
import numpy as np
from onnxmltools import convert_xgboost
from onnxmltools.convert.common.data_types import FloatTensorType

# load trained model
model = joblib.load("models/trained//xgboost/xgboost_congestion.pkl")

# load feature schema
with open("models/trained/xgboost/xgboost_congestion_features.json") as f:
    feature_names = json.load(f)

# define input shape
initial_type = [("input", FloatTensorType([None, len(feature_names)]))]

# convert
onnx_model = convert_xgboost(model, initial_types=initial_type)

# save
with open("edge/raspberry_pi/models/xgboost_congestion.onnx", "wb") as f:
    f.write(onnx_model.SerializeToString())