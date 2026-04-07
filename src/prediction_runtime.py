from __future__ import annotations

import random
from typing import Any, Dict, Tuple

from src.player_source import resolve_player_row
from src.predictor import ApexPredictor


def format_percent(value: float) -> str:
    return f"{value * 100:.2f}%"


def clamp(value: float, low: float, high: float) -> float:
    return min(max(value, low), high)


def build_estimated_recent_games(
    row: Dict[str, Any],
    rank_confidence: float,
    promotion_chance: float,
    demotion_risk: float,
) -> list[Dict[str, Any]]:
    player_sig = f"{row.get('player','')}-{row.get('uid','')}-{int(float(row.get('level', 0) or 0))}"
    rng = random.Random(player_sig)

    games_played = float(row.get("games_played", 0) or 0)
    wins = float(row.get("wins", 0) or 0)
    observed_wr = wins / games_played if games_played > 0 else 0.0
    kdr = float(row.get("kdr", 0) or 0)
    rank_score = float(row.get("rank_score", 0) or 0)

    model_wr_proxy = clamp(
        0.04
        + rank_confidence * 0.42
        + promotion_chance * 0.20
        - demotion_risk * 0.08
        + min(3.0, max(0.0, kdr)) * 0.05,
        0.01,
        0.75,
    )
    wr = clamp(0.65 * observed_wr + 0.35 * model_wr_proxy, 0.01, 0.75)

    observed_dpg = float(row.get("damage_per_game", 0) or 0)
    damage_proxy = 120.0 + min(2200.0, rank_score * 0.02) + min(700.0, max(0.0, kdr) * 180.0)
    base_damage = observed_dpg if observed_dpg > 0 else damage_proxy
    base_damage = clamp(base_damage, 60.0, 2800.0)

    base_kills = clamp(kdr * 1.4, 0.4, 5.5)

    out: list[Dict[str, Any]] = []
    for _ in range(5):
        form = clamp(rng.gauss(1.0, 0.25), 0.5, 1.8)
        p_win = clamp(wr * form, 0.01, 0.85)
        roll = rng.random()

        if roll < p_win:
            placement = 1
            outcome = "Win"
        elif roll < min(0.98, p_win + 0.22):
            placement = int(rng.randint(2, 5))
            outcome = "Top 5"
        elif roll < min(0.99, p_win + 0.55):
            placement = int(rng.randint(6, 10))
            outcome = "Top 10"
        else:
            placement = int(rng.randint(11, 20))
            outcome = "Early/Mid"

        kills = int(round(clamp(base_kills * form * rng.uniform(0.7, 1.35), 0.0, 14.0)))
        damage = clamp(base_damage * form * rng.uniform(0.75, 1.25), 40.0, 4200.0)

        out.append(
            {
                "placement": placement,
                "kills": kills,
                "damage": round(damage, 0),
                "outcome": outcome,
                "source": "estimate",
            }
        )

    return out


def run_prediction(player_name: str, platform: str) -> Tuple[Dict[str, Any], Dict[str, Any], float]:
    row, source = resolve_player_row(
        player_name=player_name,
        platform=platform,
        source_mode="auto",
    )

    predictor = ApexPredictor("model/model.pkl")
    pred = predictor.predict(row)
    rank_confidence = float(pred.get("rank_confidence", 0.0))
    promotion_chance = float(pred.get("promotion_chance", 0.0))
    demotion_risk = float(pred.get("demotion_risk", 0.0))

    result = {
        "player": row["player"],
        "rank": pred["predicted_rank"],
        "rank_confidence": format_percent(rank_confidence),
        "promotion_chance": format_percent(promotion_chance),
        "demotion_risk": format_percent(demotion_risk),
        "rank_profile": [
            {
                "rank": str(item.get("rank", "Unknown")),
                "probability": float(item.get("probability", 0.0)),
                "percent": format_percent(float(item.get("probability", 0.0))),
            }
            for item in pred.get("rank_profile", [])
        ],
        "source": source,
        "best_map": pred["best_map"],
        "best_legend": pred["best_legend"],
        "best_drop_zone": pred["best_drop_zone"],
        "ideal_team_role": pred["ideal_team_role"],
        "combat_style": pred["combat_style"],
    }

    recent_matches = row.get("recent_matches") if isinstance(row.get("recent_matches"), list) else []
    if recent_matches:
        result["recent_games"] = recent_matches[:5]
        result["recent_games_kind"] = "api"
    else:
        result["recent_games"] = build_estimated_recent_games(
            row=row,
            rank_confidence=rank_confidence,
            promotion_chance=promotion_chance,
            demotion_risk=demotion_risk,
        )
        result["recent_games_kind"] = "estimate"

    player_stats = {
        "level": int(row.get("level", 0)),
        "rank_score": int(row.get("rank_score", 0)),
        "kills": int(row.get("kills", 0)),
        "wins": int(row.get("wins", 0)),
    }
    confidence_score = round(rank_confidence * 100.0, 2)
    return result, player_stats, confidence_score
