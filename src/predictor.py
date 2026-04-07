from pathlib import Path
from typing import Any, Dict

import joblib
import numpy as np
import pandas as pd

from src.predictor_logic import (
    as_float,
    build_recommendations,
    clamp,
    compute_rank_metrics,
    pick_from_scored,
    rank_tier_score,
)


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
        self.win_rate_model = bundle.get("win_rate_model")
        self.label_encoder = bundle.get("label_encoder")
        self.feature_columns = bundle.get("feature_columns")

        if not all([self.rank_model, self.label_encoder, self.feature_columns]):
            raise PredictorError("Model bundle missing required keys.")

    def _build_features(self, player_row: Dict[str, Any]) -> pd.DataFrame:
        values = {}
        for col in self.feature_columns:
            values[col] = float(player_row.get(col, 0.0))

        return pd.DataFrame([values], columns=self.feature_columns)

    @staticmethod
    def _as_float(value: Any, default: float = 0.0) -> float:
        return as_float(value, default)

    @staticmethod
    def _clamp(value: float, low: float, high: float) -> float:
        return clamp(value, low, high)

    @staticmethod
    def _pick_from_scored(scored: Dict[str, float], signature: int, top_k: int = 2) -> str:
        return pick_from_scored(scored=scored, signature=signature, top_k=top_k)

    @staticmethod
    def _rank_tier_score(rank_name: str) -> int:
        return rank_tier_score(rank_name)

    def _rank_metrics(self, X: pd.DataFrame, predicted_rank: str, player_row: Dict[str, Any]) -> Dict[str, float]:
        _ = predicted_rank
        return compute_rank_metrics(
            rank_model=self.rank_model,
            label_encoder=self.label_encoder,
            X=X,
            player_row=player_row,
        )

    def _recommendations(self, player_row: Dict[str, Any]) -> Dict[str, str]:
        return build_recommendations(player_row)

    def predict(self, player_row: Dict[str, Any]) -> Dict[str, Any]:
        X = self._build_features(player_row)

        rank_idx = int(self.rank_model.predict(X)[0])
        rank_name = self.label_encoder.inverse_transform(np.array([rank_idx]))[0]
        rank_metrics = self._rank_metrics(X, predicted_rank=rank_name, player_row=player_row)

        return {
            "predicted_rank": rank_name,
            "rank_confidence": rank_metrics["rank_confidence"],
            "promotion_chance": rank_metrics["promotion_chance"],
            "demotion_risk": rank_metrics["demotion_risk"],
            "rank_profile": rank_metrics.get("rank_profile", []),
            **self._recommendations(player_row),
        }
