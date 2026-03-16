from pathlib import Path
from typing import Any, Dict

import joblib
import numpy as np
import pandas as pd


class PredictorError(Exception):
    """Raised when prediction cannot be performed."""


class ApexPredictor:
    def __init__(self, model_path: str = "model/model.pkl") -> None:
        path = Path(model_path)
        if not path.exists():
            raise PredictorError(f"Model file not found: {model_path}")

        bundle = joblib.load(path)
        if not isinstance(bundle, dict):
            raise PredictorError("Model bundle is invalid. Expected dict with model artifacts.")

        self.rank_model = bundle.get("rank_model")
        self.damage_model = bundle.get("damage_model")
        self.label_encoder = bundle.get("label_encoder")
        self.feature_columns = bundle.get("feature_columns")

        if not all([self.rank_model, self.damage_model, self.label_encoder, self.feature_columns]):
            raise PredictorError("Model bundle missing required keys.")

    def _build_features(self, player_row: Dict[str, Any]) -> pd.DataFrame:
        values = {}
        for col in self.feature_columns:
            values[col] = float(player_row.get(col, 0.0))

        return pd.DataFrame([values], columns=self.feature_columns)

    def predict(self, player_row: Dict[str, Any]) -> Dict[str, Any]:
        X = self._build_features(player_row)

        rank_idx = int(self.rank_model.predict(X)[0])
        rank_name = self.label_encoder.inverse_transform(np.array([rank_idx]))[0]
        damage_pred = float(self.damage_model.predict(X)[0])

        return {
            "predicted_rank": rank_name,
            "predicted_damage_per_game": max(0.0, damage_pred),
        }
