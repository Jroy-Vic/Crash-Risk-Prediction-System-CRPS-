# tools/analyze_logs.py

import pandas as pd
from pathlib import Path

LOG_PATH = Path("logs/crps_predictions.csv")

def main():
    if not LOG_PATH.exists():
        print("No log file found.")
        return

    df = pd.read_csv(LOG_PATH)

    print("\n=== CRPS LOG SUMMARY ===")
    print(f"Rows: {len(df)}")

    if len(df) == 0:
        return

    print("\nRisk counts:")
    print(df["risk_level"].value_counts(dropna=False))

    print("\nMode counts:")
    print(df["mode"].value_counts(dropna=False))

    print("\nBackend status:")
    print(df["backend_status"].value_counts(dropna=False))

    bad_probs = df[
        (df["probability"] < 0) |
        (df["probability"] > 1)
    ]

    bad_speeds = df[
        df["recommended_speed_mph"] > df["speed_limit_mph"]
    ]

    print("\nValidation checks:")
    print(f"Bad probabilities: {len(bad_probs)}")
    print(f"Speed cap violations: {len(bad_speeds)}")

    if "speed_ratio" in df.columns:
        print("\nAverage speed ratio by risk:")
        print(df.groupby("risk_level")["speed_ratio"].mean())

    errors = df[df["error"].notna() & (df["error"] != "")]
    print(f"\nErrors logged: {len(errors)}")

    if len(errors):
        print(errors[["timestamp", "mode", "backend_status", "error"]].tail(10))


if __name__ == "__main__":
    main()