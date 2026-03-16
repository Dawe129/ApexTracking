from __future__ import annotations

from flask import Flask, render_template, request

from src.collector import CollectorError, fetch_player_stats, load_api_key, player_to_row
from src.predictor import ApexPredictor, PredictorError

app = Flask(__name__)


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
            api_key = load_api_key()
            payload = fetch_player_stats(player=player_name, api_key=api_key, platform=platform)
            row = player_to_row(payload, requested_name=player_name)

            predictor = ApexPredictor("model/model.pkl")
            pred = predictor.predict(row)

            context["result"] = {
                "player": row["player"],
                "rank": pred["predicted_rank"],
                "damage_per_game": _format_value(pred["predicted_damage_per_game"]),
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
