from __future__ import annotations

from typing import Any, Dict

import numpy as np
import pandas as pd


def as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def clamp(value: float, low: float, high: float) -> float:
    return min(max(value, low), high)


def pick_from_scored(scored: Dict[str, float], signature: int, top_k: int = 2) -> str:
    ordered = sorted(scored.items(), key=lambda kv: (-kv[1], kv[0]))
    if not ordered:
        return "Unknown"
    top = ordered[: max(1, min(top_k, len(ordered)))]
    return top[signature % len(top)][0]


def rank_tier_score(rank_name: str) -> int:
    norm = str(rank_name or "").strip().lower()

    if "predator" in norm:
        base = 9
    elif "master" in norm:
        base = 8
    elif "diamond" in norm:
        base = 7
    elif "platinum" in norm or "plat" in norm:
        base = 6
    elif "gold" in norm:
        base = 5
    elif "silver" in norm:
        base = 4
    elif "bronze" in norm:
        base = 3
    elif "rookie" in norm:
        base = 2
    elif "unranked" in norm:
        base = 1
    else:
        base = 0

    if " iv" in f" {norm} ":
        div = 0
    elif " iii" in f" {norm} ":
        div = 1
    elif " ii" in f" {norm} ":
        div = 2
    elif " i" in f" {norm} ":
        div = 3
    else:
        div = 0

    return base * 10 + div


def compute_rank_metrics(
    rank_model: Any,
    label_encoder: Any,
    X: pd.DataFrame,
    player_row: Dict[str, Any],
) -> Dict[str, float]:
    if hasattr(rank_model, "predict_proba"):
        probs = np.asarray(rank_model.predict_proba(X)[0], dtype=float)
    else:
        probs = np.zeros(len(label_encoder.classes_), dtype=float)
        pred_idx = int(rank_model.predict(X)[0])
        if 0 <= pred_idx < len(probs):
            probs[pred_idx] = 1.0

    confidence = float(np.max(probs)) if probs.size else 0.0
    confidence = clamp(confidence, 0.0, 1.0)

    current_rank = str(player_row.get("rank", "Unranked"))
    current_score = rank_tier_score(current_rank)

    promotion = 0.0
    demotion = 0.0
    for idx, cls_name in enumerate(label_encoder.classes_):
        cls_score = rank_tier_score(str(cls_name))
        p = float(probs[idx]) if idx < len(probs) else 0.0
        if cls_score > current_score:
            promotion += p
        elif cls_score < current_score:
            demotion += p

    return {
        "rank_confidence": confidence,
        "promotion_chance": clamp(promotion, 0.0, 1.0),
        "demotion_risk": clamp(demotion, 0.0, 1.0),
    }


def build_recommendations(player_row: Dict[str, Any]) -> Dict[str, str]:
    kdr = as_float(player_row.get("kdr", 0.0))
    damage_per_game = as_float(player_row.get("damage_per_game", 0.0))
    kills = as_float(player_row.get("kills", 0.0))
    wins = as_float(player_row.get("wins", 0.0))
    headshots = as_float(player_row.get("headshots", 0.0))
    rank_score = as_float(player_row.get("rank_score", 0.0))
    games_played = max(1.0, as_float(player_row.get("games_played", 0.0)))

    aggression_score = clamp(
        min(2.0, kdr) * 1.8
        + min(1500.0, damage_per_game) / 700.0
        + min(12000.0, kills) / 9000.0
        + min(5000.0, headshots) / 4000.0,
        0.0,
        6.0,
    )
    macro_score = clamp(
        min(20000.0, rank_score) / 5500.0 + min(3000.0, wins) / 1000.0,
        0.0,
        6.0,
    )
    survival_score = clamp((wins / games_played) * 30.0 + macro_score * 0.4, 0.0, 6.0)

    signature = int(
        as_float(player_row.get("level"), 0.0)
        + as_float(player_row.get("wins"), 0.0) * 3
        + as_float(player_row.get("kills"), 0.0) * 0.1
        + as_float(player_row.get("rank_score"), 0.0) * 0.01
    )

    map_scores = {
        "World's Edge": aggression_score * 1.05 + macro_score * 0.55,
        "Olympus": aggression_score * 0.95 + survival_score * 0.4,
        "Storm Point": macro_score * 1.1 + survival_score * 0.8,
        "Kings Canyon": aggression_score * 0.7 + survival_score * 0.65,
        "Broken Moon": macro_score * 0.9 + aggression_score * 0.55,
    }
    best_map = pick_from_scored(map_scores, signature=signature, top_k=2)

    legend_scores = {
        "Wraith": aggression_score * 1.2,
        "Horizon": aggression_score * 1.05 + macro_score * 0.35,
        "Bangalore": aggression_score * 0.7 + survival_score * 0.8,
        "Valkyrie": macro_score * 1.15,
        "Bloodhound": aggression_score * 0.65 + macro_score * 0.75,
        "Conduit": survival_score * 1.05 + macro_score * 0.55,
    }
    best_legend = pick_from_scored(legend_scores, signature=signature + 1, top_k=3)

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
    ideal_team_role = pick_from_scored(role_scores, signature=signature + 3, top_k=2)

    style_scores = {
        "High tempo push": aggression_score * 1.2,
        "Skirmish and isolate": aggression_score * 1.0 + macro_score * 0.35,
        "Zone control and rotations": macro_score * 1.2 + survival_score * 0.5,
        "Safe scaling and resets": survival_score * 1.1,
        "Mid-game power spikes": macro_score * 0.8 + aggression_score * 0.7,
    }
    combat_style = pick_from_scored(style_scores, signature=signature + 4, top_k=2)

    return {
        "best_map": best_map,
        "best_legend": best_legend,
        "best_drop_zone": best_drop_zone,
        "ideal_team_role": ideal_team_role,
        "combat_style": combat_style,
    }
