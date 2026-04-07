from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

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
from src.apex_api import CollectorError
from src.leaderboard import load_leaderboard
from src.prediction_runtime import run_prediction
from src.predictor import PredictorError

PROJECT_ROOT = Path(__file__).resolve().parent.parent
app = Flask(
    __name__,
    template_folder=str(PROJECT_ROOT / "templates"),
    static_folder=str(PROJECT_ROOT / "static"),
)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret-change-me")

init_db()


def _load_current_user() -> Dict[str, Any] | None:
    user_id = session.get("user_id")
    if not user_id:
        return None
    return get_user_by_id(int(user_id))


def _resolve_ui_mode(user: Dict[str, Any] | None) -> tuple[bool, str, bool]:
    is_guest = bool(session.get("guest")) and user is None
    if user is not None:
        ui_mode = "user"
    elif is_guest:
        ui_mode = "guest"
    else:
        ui_mode = "auth"
    return is_guest, ui_mode, ui_mode in {"guest", "user"}


def _build_context(user: Dict[str, Any] | None) -> Dict[str, Any]:
    leaderboard = load_leaderboard(limit=50)
    is_guest, ui_mode, can_use_search = _resolve_ui_mode(user)
    history = get_recent_predictions(user["id"], limit=12) if user else []
    return {
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


def _save_prediction(user_id: int, queried_player: str, result: Dict[str, Any], confidence_score: float) -> None:
    save_user_prediction(
        user_id=user_id,
        queried_player=queried_player,
        resolved_player=result["player"],
        predicted_rank=result["rank"],
        predicted_damage_per_game=confidence_score,
        source=result["source"],
    )


def _apply_prediction(context: Dict[str, Any], player_name: str, platform: str, user: Dict[str, Any] | None) -> None:
    result, player_stats, confidence_score = run_prediction(player_name, platform)
    context["player_name"] = player_name
    context["platform"] = platform
    context["result"] = result
    context["player_stats"] = player_stats
    if user is not None:
        _save_prediction(user_id=user["id"], queried_player=player_name, result=result, confidence_score=confidence_score)
        context["history"] = get_recent_predictions(user["id"], limit=12)


@app.route("/", methods=["GET", "POST"])
def index():
    user = _load_current_user()
    context = _build_context(user)

    # One-time auto-load of linked Apex account right after successful login.
    if request.method == "GET" and user is not None and (user.get("apex_player") or "").strip():
        should_autoload = bool(session.pop("autoload_my_account", False))
        if should_autoload:
            own_player = (user.get("apex_player") or "").strip()
            own_platform = (user.get("apex_platform") or "PC").strip().upper()
            try:
                _apply_prediction(context=context, player_name=own_player, platform=own_platform, user=user)
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
        is_guest, ui_mode, can_use_search = _resolve_ui_mode(user)

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
                _apply_prediction(context=context, player_name=own_player, platform=own_platform, user=user)
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
            _apply_prediction(context=context, player_name=player_name, platform=platform, user=user)
        except (CollectorError, PredictorError, OSError, ValueError) as exc:
            context["error"] = str(exc)

    return render_template("index.html", **context)


def main() -> None:
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=False)


if __name__ == "__main__":
    main()
