import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[2]))

from src.models.train_xgboost import model, preds, X_train_copy, y_val, feature_names, importance
from sklearn.metrics import classification_report
import matplotlib.pyplot as plt
import pandas as pd
import xgboost as xgb


for i, col in enumerate(X_train_copy.columns):
    print(i, col)

print(classification_report(y_val, preds))

feat_df = pd.DataFrame({
    "feature": feature_names,
    "importance": importance
}).sort_values(by="importance", ascending=False)

print(feat_df.head(20))

xgb.plot_importance(model, importance_type="gain")
plt.show()

