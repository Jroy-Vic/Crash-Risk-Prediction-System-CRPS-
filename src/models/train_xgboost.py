import polars as pl
import pandas as pd
import xgboost as xgb
import json

# Load data
train = pl.read_parquet("data/splits/train.parquet")
val   = pl.read_parquet("data/splits/val.parquet")

# Drop non-feature columns
drop_cols = [
    "timestamp",
    "timestamp_hour",
    "segment_id",
    "station_id",
    "speed_ratio",             # remove to force model to learn from raw speed and free flow speed
    "speed_mph",               # remove to force model to learn from raw speed and free flow speed
    "free_flow_speed_mph",     # remove to force model to learn from raw speed and free flow speed
    "congestion_now",          # remove
    "crash_label_future",      # remove (critical)
]

X_train = train.drop(drop_cols + ["congestion_label_future"])
X_train_copy = X_train.clone()  # for feature importance analysis later
y_train = train["congestion_label_future"]
feature_names = X_train.columns

X_val = val.drop(drop_cols + ["congestion_label_future"])
y_val = val["congestion_label_future"]

with open("models/trained/xgboost/xgboost_congestion_features.json", "w") as f:
    json.dump(list(feature_names), f, indent=2)

# Convert to numpy
X_train = X_train.to_numpy()
y_train = y_train.to_numpy()

X_val = X_val.to_numpy()
y_val = y_val.to_numpy()

# Model
model = xgb.XGBClassifier(
    n_estimators=100,
    max_depth=6,
    learning_rate=0.1,
    scale_pos_weight=20  # handle imbalance
)

model.fit(X_train, y_train)
importance = model.feature_importances_

# Save model
import joblib
joblib.dump(model, "models/trained/xgboost/xgboost_congestion.pkl")

# Predictions
probs = model.predict_proba(X_val)[:, 1]
preds = (probs > 0.7).astype(int)
