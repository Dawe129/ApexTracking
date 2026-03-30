from __future__ import annotations

from pathlib import Path

from flask import Flask, render_template, request

from src.collector import CollectorError
from src.player_source import resolve_player_row
from src.predictor import ApexPredictor, PredictorError

PROJECT_ROOT = Path(__file__).resolve().parent.parent
app = Flask(
    __name__,
    template_folder=str(PROJECT_ROOT / "templates"),
    static_folder=str(PROJECT_ROOT / "static"),
)


def _format_value(value: float) -> str:
    return f"{value:,.2f}".replace(",", " ")


@app.route("/", methods=["GET", "POST"])
def index():
    context = {
        "player_name": "",
        "platform": "PC",
        "error": None,
        "result": None,
        "player_stats": None,
    }

    if request.method == "POST":
        player_name = (request.form.get("player_name") or "").strip()
        platform = (request.form.get("platform") or "PC").strip().upper()

        context["player_name"] = player_name
        context["platform"] = platform

        if not player_name:
            context["error"] = "Vypln jmeno hrace."
            return render_template("index.html", **context)

        try:
            row, source = resolve_player_row(
                player_name=player_name,
                platform=platform,
                source_mode="auto",
            )

            predictor = ApexPredictor("model/model.pkl")
            pred = predictor.predict(row)

            context["result"] = {
                "player": row["player"],
                "rank": pred["predicted_rank"],
                "damage_per_game": _format_value(pred["predicted_damage_per_game"]),
                "source": source,
                "best_map": pred["best_map"],
                "best_legend": pred["best_legend"],
                "best_drop_zone": pred["best_drop_zone"],
                "ideal_team_role": pred["ideal_team_role"],
                "combat_style": pred["combat_style"],
            }
            context["player_stats"] = {
                "level": int(row.get("level", 0)),
                "rank_score": int(row.get("rank_score", 0)),
                "kills": int(row.get("kills", 0)),
                "wins": int(row.get("wins", 0)),
            }
        except (CollectorError, PredictorError, OSError, ValueError) as exc:
            context["error"] = str(exc)

    return render_template("index.html", **context)


def main() -> None:
    app.run(host="127.0.0.1", port=5000, debug=False)


if __name__ == "__main__":
    main()
