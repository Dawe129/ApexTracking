from __future__ import annotations

from typing import Any, Dict, List


def coerce_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def extract_nested_value(data: Dict[str, Any], path: List[str], fallback: float = 0.0) -> float:
    current: Any = data
    for key in path:
        if not isinstance(current, dict):
            return fallback
        current = current.get(key)
    if isinstance(current, dict):
        return coerce_float(current.get("value"), fallback)
    return coerce_float(current, fallback)


def extract_first_value(data: Dict[str, Any], paths: List[List[str]], fallback: float = 0.0) -> float:
    for path in paths:
        value = extract_nested_value(data, path, fallback=float("nan"))
        if not (isinstance(value, float) and value != value):
            return value
    return fallback


def _extract_recent_matches(payload: Dict[str, Any], limit: int = 5) -> List[Dict[str, Any]]:
    if not isinstance(payload, dict):
        return []

    candidates: List[Any] = []
    for key in ["matches", "match_history", "history", "recent_matches", "gameHistory"]:
        value = payload.get(key)
        if isinstance(value, list):
            candidates.extend(value)

    if not candidates:
        global_stats = payload.get("global")
        if isinstance(global_stats, dict):
            for key in ["matches", "match_history", "history", "recent_matches", "gameHistory"]:
                value = global_stats.get(key)
                if isinstance(value, list):
                    candidates.extend(value)

    out: List[Dict[str, Any]] = []
    for item in candidates:
        if not isinstance(item, dict):
            continue

        placement = int(coerce_float(item.get("placement") or item.get("place") or item.get("rank"), default=0))
        kills = int(coerce_float(item.get("kills") or item.get("kill_count"), default=0))
        damage = coerce_float(item.get("damage") or item.get("damageDealt"), default=0.0)

        if placement <= 0:
            placement = 20

        out.append(
            {
                "placement": placement,
                "kills": max(0, kills),
                "damage": max(0.0, damage),
                "outcome": "Win" if placement == 1 else ("Top 5" if placement <= 5 else "Mid/Late"),
                "source": "api",
            }
        )

    return out[:limit]


def extract_selected_legend_tracker_value(payload: Dict[str, Any], tracker_tokens: List[str]) -> float:
    legends = payload.get("legends") if isinstance(payload, dict) else None
    if not isinstance(legends, dict):
        return 0.0

    selected = legends.get("selected")
    if not isinstance(selected, dict):
        return 0.0

    data = selected.get("data")
    if not isinstance(data, list):
        return 0.0

    best = 0.0
    tokens = [t.lower() for t in tracker_tokens]

    for entry in data:
        if not isinstance(entry, dict):
            continue

        label = " ".join(
            [
                str(entry.get("name", "")),
                str(entry.get("key", "")),
                str(entry.get("keyName", "")),
            ]
        ).lower()
        if not any(token in label for token in tokens):
            continue

        value = coerce_float(entry.get("value"), default=0.0)
        if value > best:
            best = value

    return best


def player_to_row(payload: Dict[str, Any], requested_name: str = "") -> Dict[str, Any]:
    global_stats = payload.get("global", {}) if isinstance(payload, dict) else {}
    total_stats = payload.get("total", {}) if isinstance(payload, dict) else {}

    player_name = global_stats.get("name") or requested_name or "unknown"
    uid = global_stats.get("uid", "")
    level = coerce_float(global_stats.get("level"))

    rank_info = global_stats.get("rank", {}) if isinstance(global_stats, dict) else {}
    rank_name = rank_info.get("rankName", "Unknown") if isinstance(rank_info, dict) else "Unknown"
    rank_div = rank_info.get("rankDiv", "") if isinstance(rank_info, dict) else ""
    rank_score = coerce_float(rank_info.get("rankScore")) if isinstance(rank_info, dict) else 0.0

    kills = extract_nested_value(total_stats, ["kills"])
    damage = extract_nested_value(total_stats, ["damage"])
    headshots = extract_nested_value(total_stats, ["headshots"])
    games_played = extract_first_value(
        total_stats,
        paths=[["games_played"], ["matchesplayed"], ["matches_played"]],
        fallback=0.0,
    )
    wins = extract_first_value(total_stats, paths=[["wins"], ["matcheswon"], ["matches_won"]], fallback=0.0)
    kd_from_total = extract_first_value(total_stats, paths=[["kd"], ["kdr"]], fallback=0.0)

    if kills <= 0:
        kills = extract_selected_legend_tracker_value(payload, tracker_tokens=["kill"])
    if wins <= 0:
        wins = extract_selected_legend_tracker_value(payload, tracker_tokens=["win"])

    if games_played <= 0 and kills > 0 and kd_from_total > 0:
        games_played = kills / kd_from_total

    if games_played <= 0 and (kills > 0 or damage > 0):
        games_played = max(
            level * 8.0,
            kills,
            wins * 15.0,
            1.0,
        )

    kdr = kills / games_played if games_played > 0 else 0.0
    damage_per_game = damage / games_played if games_played > 0 else 0.0

    return {
        "player": player_name,
        "uid": uid,
        "level": level,
        "rank": rank_name,
        "rank_div": rank_div,
        "rank_score": rank_score,
        "kills": kills,
        "damage": damage,
        "headshots": headshots,
        "games_played": games_played,
        "wins": wins,
        "kdr": kdr,
        "damage_per_game": damage_per_game,
        "recent_matches": _extract_recent_matches(payload, limit=5),
    }


def row_nonzero_metric_count(row: Dict[str, Any]) -> int:
    metrics = [
        coerce_float(row.get("kills")),
        coerce_float(row.get("damage")),
        coerce_float(row.get("games_played")),
        coerce_float(row.get("wins")),
        coerce_float(row.get("headshots")),
        coerce_float(row.get("rank_score")),
    ]
    return sum(1 for value in metrics if value > 0)


def is_row_usable(
    row: Dict[str, Any],
    min_level: float = 25.0,
    min_kills: float = 80.0,
    min_damage: float = 20000.0,
    min_rank_score: float = 1000.0,
    min_nonzero_metrics: int = 3,
    require_gameplay_signal: bool = True,
) -> bool:
    level = coerce_float(row.get("level"))
    kills = coerce_float(row.get("kills"))
    damage = coerce_float(row.get("damage"))
    games_played = coerce_float(row.get("games_played"))
    wins = coerce_float(row.get("wins"))
    headshots = coerce_float(row.get("headshots"))
    rank_score = coerce_float(row.get("rank_score"))

    if level < min_level:
        return False

    if row_nonzero_metric_count(row) < min_nonzero_metrics:
        return False

    if require_gameplay_signal and (games_played <= 0 and damage <= 0 and wins <= 0 and headshots <= 0):
        return False

    if kills < min_kills and damage < min_damage and games_played <= 0 and rank_score < min_rank_score:
        return False

    return True
