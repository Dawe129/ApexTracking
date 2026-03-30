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

    @staticmethod
    def _as_float(value: Any, default: float = 0.0) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def _recommendations(self, player_row: Dict[str, Any]) -> Dict[str, str]:
        kdr = self._as_float(player_row.get("kdr", 0.0))
        damage_per_game = self._as_float(player_row.get("damage_per_game", 0.0))
        kills = self._as_float(player_row.get("kills", 0.0))
        wins = self._as_float(player_row.get("wins", 0.0))
        headshots = self._as_float(player_row.get("headshots", 0.0))
        rank_score = self._as_float(player_row.get("rank_score", 0.0))

        aggression_score = (
            min(2.0, kdr) * 1.8
            + min(1500.0, damage_per_game) / 700.0
            + min(12000.0, kills) / 9000.0
            + min(5000.0, headshots) / 4000.0
        )
        macro_score = min(18000.0, rank_score) / 6000.0 + min(3000.0, wins) / 1200.0

        if aggression_score >= 4.2:
            best_map = "World's Edge"
            best_legend = "Wraith"
            best_drop_zone = "Fragment East"
            ideal_team_role = "Entry fragger"
            combat_style = "High tempo push"
        elif aggression_score >= 3.2:
            best_map = "Olympus"
            best_legend = "Horizon"
            best_drop_zone = "Estates"
            ideal_team_role = "Flex fragger"
            combat_style = "Skirmish and isolate"
        elif macro_score >= 2.8:
            best_map = "Storm Point"
            best_legend = "Valkyrie"
            best_drop_zone = "Checkpoint"
            ideal_team_role = "Macro IGL"
            combat_style = "Zone control and rotations"
        else:
            best_map = "Kings Canyon"
            best_legend = "Bangalore"
            best_drop_zone = "Repulsor"
            ideal_team_role = "Support anchor"
            combat_style = "Safe scaling and resets"

        return {
            "best_map": best_map,
            "best_legend": best_legend,
            "best_drop_zone": best_drop_zone,
            "ideal_team_role": ideal_team_role,
            "combat_style": combat_style,
        }

    def _calibrate_damage_prediction(self, raw_pred: float, player_row: Dict[str, Any]) -> float:
        # Keep prediction in a realistic range and anchor it to observed stats when available.
        raw = max(0.0, float(raw_pred))

        observed = self._as_float(player_row.get("damage_per_game"), 0.0)
        if observed <= 0:
            total_damage = self._as_float(player_row.get("damage"), 0.0)
            games_played = self._as_float(player_row.get("games_played"), 0.0)
            if total_damage > 0 and games_played > 0:
                observed = total_damage / games_played

        if observed > 0:
            observed = min(max(observed, 0.0), 4000.0)
            diff_ratio = abs(raw - observed) / max(observed, 1.0)
            weight_observed = 0.75 if diff_ratio > 1.0 else 0.60
            calibrated = weight_observed * observed + (1.0 - weight_observed) * raw
        else:
            calibrated = raw

        return min(max(calibrated, 0.0), 4000.0)

    def predict(self, player_row: Dict[str, Any]) -> Dict[str, Any]:
        X = self._build_features(player_row)

        rank_idx = int(self.rank_model.predict(X)[0])
        rank_name = self.label_encoder.inverse_transform(np.array([rank_idx]))[0]
        damage_pred = float(self.damage_model.predict(X)[0])
        damage_pred = self._calibrate_damage_prediction(damage_pred, player_row)

        return {
            "predicted_rank": rank_name,
            "predicted_damage_per_game": max(0.0, damage_pred),
            **self._recommendations(player_row),
        }
