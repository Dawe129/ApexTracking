from __future__ import annotations

import os
import random
from pathlib import Path
from typing import Any, Dict, Tuple

from flask import Flask, redirect, render_template, request, session, url_for

from src.auth_store import (
    authenticate_user,
    create_user,
    get_recent_predictions,
    get_user_by_id,
    init_db,
    save_user_prediction,
    update_user_apex_profile,
)
from src.collector import CollectorError
from src.leaderboard import load_leaderboard
from src.player_source import resolve_player_row
from src.predictor import ApexPredictor, PredictorError

PROJECT_ROOT = Path(__file__).resolve().parent.parent
app = Flask(
    __name__,
    template_folder=str(PROJECT_ROOT / "templates"),
    static_folder=str(PROJECT_ROOT / "static"),
)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret-change-me")

init_db()


def _format_value(value: float) -> str:
    return f"{value:,.2f}".replace(",", " ")


def _format_percent(value: float) -> str:
    return f"{value * 100:.2f}%"


def _load_current_user() -> Dict[str, Any] | None:
    user_id = session.get("user_id")
    if not user_id:
        return None
    return get_user_by_id(int(user_id))


def _clamp(value: float, low: float, high: float) -> float:
    return min(max(value, low), high)


def _build_estimated_recent_games(row: Dict[str, Any], win_rate_pred: float, damage_pred: float) -> list[Dict[str, Any]]:
    player_sig = f"{row.get('player','')}-{row.get('uid','')}-{int(float(row.get('level', 0) or 0))}"
    rng = random.Random(player_sig)

    games_played = float(row.get("games_played", 0) or 0)
    wins = float(row.get("wins", 0) or 0)
    observed_wr = wins / games_played if games_played > 0 else 0.0
    wr = _clamp(0.7 * win_rate_pred + 0.3 * observed_wr, 0.01, 0.75)

    observed_dpg = float(row.get("damage_per_game", 0) or 0)
    base_damage = observed_dpg if observed_dpg > 0 else damage_pred
    base_damage = _clamp(base_damage, 60.0, 2800.0)

    kdr = float(row.get("kdr", 0) or 0)
    base_kills = _clamp(kdr * 1.4, 0.4, 5.5)

    out: list[Dict[str, Any]] = []
    for _ in range(5):
        form = _clamp(rng.gauss(1.0, 0.25), 0.5, 1.8)
        p_win = _clamp(wr * form, 0.01, 0.85)
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

        kills = int(round(_clamp(base_kills * form * rng.uniform(0.7, 1.35), 0.0, 14.0)))
        damage = _clamp(base_damage * form * rng.uniform(0.75, 1.25), 40.0, 4200.0)

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


def _run_prediction(player_name: str, platform: str) -> Tuple[Dict[str, Any], Dict[str, Any], float]:
    row, source = resolve_player_row(
        player_name=player_name,
        platform=platform,
        source_mode="auto",
    )

    predictor = ApexPredictor("model/model.pkl")
    pred = predictor.predict(row)
    damage_raw = float(pred["predicted_damage_per_game"])

    result = {
        "player": row["player"],
        "rank": pred["predicted_rank"],
        "damage_per_game": _format_value(damage_raw),
        "win_rate": _format_percent(float(pred.get("predicted_win_rate", 0.0))),
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
        result["recent_games"] = _build_estimated_recent_games(
            row=row,
            win_rate_pred=float(pred.get("predicted_win_rate", 0.0)),
            damage_pred=damage_raw,
        )
        result["recent_games_kind"] = "estimate"

    player_stats = {
        "level": int(row.get("level", 0)),
        "rank_score": int(row.get("rank_score", 0)),
        "kills": int(row.get("kills", 0)),
        "wins": int(row.get("wins", 0)),
    }
    return result, player_stats, damage_raw


@app.route("/", methods=["GET", "POST"])
def index():
    leaderboard = load_leaderboard(limit=50)
    user = _load_current_user()
    is_guest = bool(session.get("guest")) and user is None
    if user is not None:
        ui_mode = "user"
    elif is_guest:
        ui_mode = "guest"
    else:
        ui_mode = "auth"

    can_use_search = ui_mode in {"guest", "user"}
    history = get_recent_predictions(user["id"], limit=12) if user else []

    context = {
        "player_name": "",
        "platform": "PC",
        "auth_mode": "login",
        "auth_error": None,
        "auth_message": None,
        "error": None,
        "result": None,
        "player_stats": None,
        "leaderboard": leaderboard,
        "current_user": user,
        "is_guest": is_guest,
        "can_use_search": can_use_search,
        "history": history,
        "ui_mode": ui_mode,
    }

    # One-time auto-load of linked Apex account right after successful login.
    if request.method == "GET" and user is not None and (user.get("apex_player") or "").strip():
        should_autoload = bool(session.pop("autoload_my_account", False))
        if should_autoload:
            own_player = (user.get("apex_player") or "").strip()
            own_platform = (user.get("apex_platform") or "PC").strip().upper()
            try:
                result, player_stats, damage_raw = _run_prediction(own_player, own_platform)
                context["player_name"] = own_player
                context["platform"] = own_platform
                context["result"] = result
                context["player_stats"] = player_stats
                save_user_prediction(
                    user_id=user["id"],
                    queried_player=own_player,
                    resolved_player=result["player"],
                    predicted_rank=result["rank"],
                    predicted_damage_per_game=damage_raw,
                    source=result["source"],
                )
                context["history"] = get_recent_predictions(user["id"], limit=12)
            except (CollectorError, PredictorError, OSError, ValueError) as exc:
                context["error"] = str(exc)

    if request.method == "POST":
        form_action = (request.form.get("form_action") or "predict").strip().lower()

        if form_action == "register":
            email = (request.form.get("email") or "").strip()
            password = request.form.get("password") or ""
            try:
                new_user = create_user(email=email, password=password)
                session["user_id"] = new_user["id"]
                session.pop("guest", None)
                return redirect(url_for("index"))
            except (ValueError, RuntimeError) as exc:
                context["auth_mode"] = "register"
                context["auth_error"] = str(exc)
                return render_template("index.html", **context)

        if form_action == "login":
            email = (request.form.get("email") or "").strip()
            password = request.form.get("password") or ""
            logged = authenticate_user(email=email, password=password)
            if logged is None:
                context["auth_mode"] = "login"
                context["auth_error"] = "Invalid e-mail or password."
                return render_template("index.html", **context)

            session["user_id"] = logged["id"]
            session.pop("guest", None)
            session["autoload_my_account"] = True
            return redirect(url_for("index"))

        if form_action == "guest":
            session.pop("user_id", None)
            session["guest"] = True
            return redirect(url_for("index"))

        if form_action == "logout":
            session.pop("user_id", None)
            session.pop("guest", None)
            return redirect(url_for("index"))

        user = _load_current_user()
        is_guest = bool(session.get("guest")) and user is None
        if user is not None:
            ui_mode = "user"
        elif is_guest:
            ui_mode = "guest"
        else:
            ui_mode = "auth"
        can_use_search = ui_mode in {"guest", "user"}

        if form_action == "save_apex":
            if user is None:
                context["auth_error"] = "Log in first."
                return render_template("index.html", **context)

            apex_player = (request.form.get("apex_player") or "").strip()
            apex_platform = (request.form.get("apex_platform") or "PC").strip().upper()
            try:
                update_user_apex_profile(user["id"], apex_player=apex_player, apex_platform=apex_platform)
                context["auth_message"] = "Apex profile has been saved."
                user = _load_current_user()
                context["current_user"] = user
            except ValueError as exc:
                context["auth_error"] = str(exc)
            return render_template("index.html", **context)

        if form_action == "predict_my":
            if user is None:
                context["auth_error"] = "Log in first."
                return render_template("index.html", **context)

            own_player = (user.get("apex_player") or "").strip()
            own_platform = (user.get("apex_platform") or "PC").strip().upper()
            if not own_player:
                context["auth_error"] = "Save your Apex profile first."
                return render_template("index.html", **context)

            try:
                result, player_stats, damage_raw = _run_prediction(own_player, own_platform)
                context["player_name"] = own_player
                context["platform"] = own_platform
                context["result"] = result
                context["player_stats"] = player_stats
                save_user_prediction(
                    user_id=user["id"],
                    queried_player=own_player,
                    resolved_player=result["player"],
                    predicted_rank=result["rank"],
                    predicted_damage_per_game=damage_raw,
                    source=result["source"],
                )
                context["history"] = get_recent_predictions(user["id"], limit=12)
            except (CollectorError, PredictorError, OSError, ValueError) as exc:
                context["error"] = str(exc)
            return render_template("index.html", **context)

        player_name = (request.form.get("player_name") or "").strip()
        platform = (request.form.get("platform") or "PC").strip().upper()

        context["player_name"] = player_name
        context["platform"] = platform
        context["current_user"] = user
        context["is_guest"] = is_guest
        context["can_use_search"] = can_use_search
        context["ui_mode"] = ui_mode

        if not can_use_search:
            context["auth_error"] = "Log in or use guest mode."
            return render_template("index.html", **context)

        if not player_name:
            context["error"] = "Enter a player name."
            return render_template("index.html", **context)

        try:
            result, player_stats, damage_raw = _run_prediction(player_name, platform)
            context["result"] = result
            context["player_stats"] = player_stats

            if user is not None:
                save_user_prediction(
                    user_id=user["id"],
                    queried_player=player_name,
                    resolved_player=result["player"],
                    predicted_rank=result["rank"],
                    predicted_damage_per_game=damage_raw,
                    source=result["source"],
                )
                context["history"] = get_recent_predictions(user["id"], limit=12)
        except (CollectorError, PredictorError, OSError, ValueError) as exc:
            context["error"] = str(exc)

    return render_template("index.html", **context)


def main() -> None:
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=False)


if __name__ == "__main__":
    main()
