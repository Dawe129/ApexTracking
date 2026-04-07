from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

import requests
from dotenv import load_dotenv

from src.apex_payload_mapper import (
    _extract_recent_matches,
    is_row_usable,
    player_to_row,
    row_nonzero_metric_count,
)

API_URL = "https://api.mozambiquehe.re/bridge"


class CollectorError(Exception):
    """Raised when data collection fails."""


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
        "merge": "true",
    }

    try:
        response = requests.get(API_URL, params=params, timeout=timeout)
    except requests.RequestException as exc:
        raise CollectorError(f"Network error for '{player}': {exc.__class__.__name__}") from exc

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
        "merge": "true",
    }

    try:
        response = requests.get(API_URL, params=params, timeout=timeout)
    except requests.RequestException as exc:
        raise CollectorError(f"Network error for uid '{uid}': {exc.__class__.__name__}") from exc

    if response.status_code != 200:
        raise CollectorError(f"API request failed for uid '{uid}' with status {response.status_code}: {response.text}")

    payload = response.json()
    if isinstance(payload, dict) and payload.get("Error"):
        raise CollectorError(f"API error for uid '{uid}': {payload['Error']}")

    return payload


__all__ = [
    "CollectorError",
    "fetch_player_stats",
    "fetch_player_stats_by_uid",
    "is_row_usable",
    "load_api_key",
    "player_to_row",
    "row_nonzero_metric_count",
    "_extract_recent_matches",
]
