import argparse
import csv
import os
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import requests
from dotenv import load_dotenv

API_URL = "https://api.mozambiquehe.re/bridge"


class CollectorError(Exception):
    """Raised when data collection fails."""


def _coerce_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _extract_nested_value(data: Dict[str, Any], path: List[str], fallback: float = 0.0) -> float:
    current: Any = data
    for key in path:
        if not isinstance(current, dict):
            return fallback
        current = current.get(key)
    if isinstance(current, dict):
        return _coerce_float(current.get("value"), fallback)
    return _coerce_float(current, fallback)


def _extract_first_value(data: Dict[str, Any], paths: List[List[str]], fallback: float = 0.0) -> float:
    for path in paths:
        value = _extract_nested_value(data, path, fallback=float("nan"))
        if not (isinstance(value, float) and value != value):
            return value
    return fallback


def load_api_key() -> str:
    """Loads API key from env vars or a plain value in .env."""
    load_dotenv()

    explicit_key = os.getenv("APEX_API_KEY") or os.getenv("MOZAMBIQUE_API_KEY") or os.getenv("API_KEY")
    if explicit_key:
        return explicit_key.strip()

    env_path = Path(".env")
    if env_path.exists():
        raw = env_path.read_text(encoding="utf-8").strip().splitlines()
        for line in raw:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                continue
            return line

    raise CollectorError(
        "API key not found. Add APEX_API_KEY to .env or paste only the key on the first line."
    )


def fetch_player_stats(player: str, api_key: str, platform: str = "PC", timeout: int = 20) -> Dict[str, Any]:
    """Fetch one player profile from the mozambiquehe.re API."""
    params = {
        "auth": api_key,
        "player": player,
        "platform": platform,
    }

    response = requests.get(API_URL, params=params, timeout=timeout)
    if response.status_code != 200:
        raise CollectorError(f"API request failed for '{player}' with status {response.status_code}: {response.text}")

    payload = response.json()
    if isinstance(payload, dict) and payload.get("Error"):
        raise CollectorError(f"API error for '{player}': {payload['Error']}")

    return payload


def fetch_player_stats_by_uid(uid: str, api_key: str, platform: str = "PC", timeout: int = 20) -> Dict[str, Any]:
    """Fetch one player profile by UID from the mozambiquehe.re API."""
    params = {
        "auth": api_key,
        "uid": uid,
        "platform": platform,
    }

    response = requests.get(API_URL, params=params, timeout=timeout)
    if response.status_code != 200:
        raise CollectorError(f"API request failed for uid '{uid}' with status {response.status_code}: {response.text}")

    payload = response.json()
    if isinstance(payload, dict) and payload.get("Error"):
        raise CollectorError(f"API error for uid '{uid}': {payload['Error']}")

    return payload


def player_to_row(payload: Dict[str, Any], requested_name: str = "") -> Dict[str, Any]:
    """Maps API payload into a flat row for ML."""
    global_stats = payload.get("global", {}) if isinstance(payload, dict) else {}
    total_stats = payload.get("total", {}) if isinstance(payload, dict) else {}

    player_name = global_stats.get("name") or requested_name or "unknown"
    uid = global_stats.get("uid", "")
    level = _coerce_float(global_stats.get("level"))

    rank_info = global_stats.get("rank", {}) if isinstance(global_stats, dict) else {}
    rank_name = rank_info.get("rankName", "Unknown") if isinstance(rank_info, dict) else "Unknown"
    rank_div = rank_info.get("rankDiv", "") if isinstance(rank_info, dict) else ""
    rank_score = _coerce_float(rank_info.get("rankScore")) if isinstance(rank_info, dict) else 0.0

    kills = _extract_nested_value(total_stats, ["kills"])
    damage = _extract_nested_value(total_stats, ["damage"])
    headshots = _extract_nested_value(total_stats, ["headshots"])
    games_played = _extract_first_value(
        total_stats,
        paths=[["games_played"], ["matchesplayed"], ["matches_played"]],
        fallback=0.0,
    )
    wins = _extract_first_value(total_stats, paths=[["wins"], ["matcheswon"], ["matches_won"]], fallback=0.0)

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
    }


def collect_players(players: Iterable[str], out_csv: Path, api_key: str, platform: str = "PC", sleep_seconds: float = 0.3) -> int:
    """Collects data for a list of players and writes rows to CSV."""
    rows: List[Dict[str, Any]] = []
    cache: Dict[str, Dict[str, Any]] = {}

    for idx, player in enumerate(players, start=1):
        player = player.strip()
        if not player:
            continue

        cache_key = player.lower()
        if cache_key in cache:
            rows.append(dict(cache[cache_key]))
            print(f"[{idx}] OK (cached): {player}")
            continue

        try:
            payload = fetch_player_stats(player=player, api_key=api_key, platform=platform)
            row = player_to_row(payload, requested_name=player)
            cache[cache_key] = row
            rows.append(dict(row))
            print(f"[{idx}] OK: {player}")
        except CollectorError as exc:
            print(f"[{idx}] SKIP: {player} -> {exc}")

        if sleep_seconds > 0:
            time.sleep(sleep_seconds)

    if not rows:
        raise CollectorError("No rows collected. Check player names, API key, and platform.")

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    return len(rows)


def _read_players_file(file_path: Path) -> List[str]:
    if not file_path.exists():
        raise CollectorError(f"Players file does not exist: {file_path}")

    return [line.strip() for line in file_path.read_text(encoding="utf-8").splitlines() if line.strip()]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect Apex Legends player stats into CSV")
    parser.add_argument("--players-file", default="data/players_input.txt", help="Text file with one player name per line")
    parser.add_argument("--out", default="data/players.csv", help="Output CSV path")
    parser.add_argument("--platform", default="PC", help="Platform for API query (PC, PS4, X1, SWITCH)")
    parser.add_argument("--sleep", type=float, default=0.3, help="Sleep between API calls in seconds")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    api_key = load_api_key()

    players = _read_players_file(Path(args.players_file))
    count = collect_players(
        players=players,
        out_csv=Path(args.out),
        api_key=api_key,
        platform=args.platform,
        sleep_seconds=args.sleep,
    )

    print(f"Collected {count} players into {args.out}")


if __name__ == "__main__":
    main()
