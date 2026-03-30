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
        self.win_rate_model = bundle.get("win_rate_model")
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

    @staticmethod
    def _clamp(value: float, low: float, high: float) -> float:
        return min(max(value, low), high)

    @staticmethod
    def _pick_from_scored(scored: Dict[str, float], signature: int, top_k: int = 2) -> str:
        ordered = sorted(scored.items(), key=lambda kv: (-kv[1], kv[0]))
        if not ordered:
            return "Unknown"
        top = ordered[: max(1, min(top_k, len(ordered)))]
        return top[signature % len(top)][0]

    def _recommendations(self, player_row: Dict[str, Any]) -> Dict[str, str]:
        kdr = self._as_float(player_row.get("kdr", 0.0))
        damage_per_game = self._as_float(player_row.get("damage_per_game", 0.0))
        kills = self._as_float(player_row.get("kills", 0.0))
        wins = self._as_float(player_row.get("wins", 0.0))
        headshots = self._as_float(player_row.get("headshots", 0.0))
        rank_score = self._as_float(player_row.get("rank_score", 0.0))
        games_played = max(1.0, self._as_float(player_row.get("games_played", 0.0)))

        aggression_score = self._clamp(
            min(2.0, kdr) * 1.8
            + min(1500.0, damage_per_game) / 700.0
            + min(12000.0, kills) / 9000.0
            + min(5000.0, headshots) / 4000.0
            ,
            0.0,
            6.0,
        )
        macro_score = self._clamp(
            min(20000.0, rank_score) / 5500.0 + min(3000.0, wins) / 1000.0,
            0.0,
            6.0,
        )
        survival_score = self._clamp((wins / games_played) * 30.0 + macro_score * 0.4, 0.0, 6.0)

        signature = int(
            self._as_float(player_row.get("level"), 0.0)
            + self._as_float(player_row.get("wins"), 0.0) * 3
            + self._as_float(player_row.get("kills"), 0.0) * 0.1
            + self._as_float(player_row.get("rank_score"), 0.0) * 0.01
        )

        map_scores = {
            "World's Edge": aggression_score * 1.05 + macro_score * 0.55,
            "Olympus": aggression_score * 0.95 + survival_score * 0.4,
            "Storm Point": macro_score * 1.1 + survival_score * 0.8,
            "Kings Canyon": aggression_score * 0.7 + survival_score * 0.65,
            "Broken Moon": macro_score * 0.9 + aggression_score * 0.55,
        }
        best_map = self._pick_from_scored(map_scores, signature=signature, top_k=2)

        legend_scores = {
            "Wraith": aggression_score * 1.2,
            "Horizon": aggression_score * 1.05 + macro_score * 0.35,
            "Bangalore": aggression_score * 0.7 + survival_score * 0.8,
            "Valkyrie": macro_score * 1.15,
            "Bloodhound": aggression_score * 0.65 + macro_score * 0.75,
            "Conduit": survival_score * 1.05 + macro_score * 0.55,
        }
        best_legend = self._pick_from_scored(legend_scores, signature=signature + 1, top_k=3)

        drop_by_map = {
            "World's Edge": ["Fragment East", "Lava Siphon", "Skyhook"],
            "Olympus": ["Estates", "Hammond Labs", "Energy Depot"],
            "Storm Point": ["Checkpoint", "The Mill", "Barometer"],
            "Kings Canyon": ["Repulsor", "Market", "Crash Site"],
            "Broken Moon": ["Terraformer", "Promenade", "Dry Gulch"],
        }
        drop_options = drop_by_map.get(best_map, ["Center POI"])
        best_drop_zone = drop_options[(signature + 2) % len(drop_options)]

        role_scores = {
            "Entry fragger": aggression_score * 1.15,
            "Flex fragger": aggression_score * 0.95 + macro_score * 0.45,
            "Macro IGL": macro_score * 1.2,
            "Support anchor": survival_score * 1.1,
            "Recon flex": macro_score * 0.9 + aggression_score * 0.5,
        }
        ideal_team_role = self._pick_from_scored(role_scores, signature=signature + 3, top_k=2)

        style_scores = {
            "High tempo push": aggression_score * 1.2,
            "Skirmish and isolate": aggression_score * 1.0 + macro_score * 0.35,
            "Zone control and rotations": macro_score * 1.2 + survival_score * 0.5,
            "Safe scaling and resets": survival_score * 1.1,
            "Mid-game power spikes": macro_score * 0.8 + aggression_score * 0.7,
        }
        combat_style = self._pick_from_scored(style_scores, signature=signature + 4, top_k=2)

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

    def _estimate_win_rate_fallback(self, player_row: Dict[str, Any]) -> float:
        games_played = self._as_float(player_row.get("games_played"), 0.0)
        wins = self._as_float(player_row.get("wins"), 0.0)
        kdr = self._as_float(player_row.get("kdr"), 0.0)
        rank_score = self._as_float(player_row.get("rank_score"), 0.0)

        observed = wins / games_played if games_played > 0 else 0.0
        proxy = 0.02 + min(0.20, max(0.0, kdr) * 0.035) + min(0.12, max(0.0, rank_score) / 100000.0)
        if observed > 0:
            return self._clamp(observed * 0.75 + proxy * 0.25, 0.0, 0.85)
        return self._clamp(proxy, 0.0, 0.85)

    def _predict_win_rate(self, X: pd.DataFrame, player_row: Dict[str, Any]) -> float:
        if self.win_rate_model is None:
            return self._estimate_win_rate_fallback(player_row)

        raw = self._as_float(self.win_rate_model.predict(X)[0], 0.0)
        raw = self._clamp(raw, 0.0, 0.85)

        games_played = self._as_float(player_row.get("games_played"), 0.0)
        wins = self._as_float(player_row.get("wins"), 0.0)
        observed = wins / games_played if games_played > 0 else 0.0
        if observed > 0:
            diff_ratio = abs(raw - observed) / max(observed, 0.01)
            weight_observed = 0.7 if diff_ratio > 1.0 else 0.45
            return self._clamp(weight_observed * observed + (1.0 - weight_observed) * raw, 0.0, 0.85)

        return raw

    def predict(self, player_row: Dict[str, Any]) -> Dict[str, Any]:
        X = self._build_features(player_row)

        rank_idx = int(self.rank_model.predict(X)[0])
        rank_name = self.label_encoder.inverse_transform(np.array([rank_idx]))[0]
        damage_pred = float(self.damage_model.predict(X)[0])
        damage_pred = self._calibrate_damage_prediction(damage_pred, player_row)
        win_rate_pred = self._predict_win_rate(X, player_row)

        return {
            "predicted_rank": rank_name,
            "predicted_damage_per_game": max(0.0, damage_pred),
            "predicted_win_rate": win_rate_pred,
            **self._recommendations(player_row),
        }
