import unittest

from src.prediction_runtime import build_estimated_recent_games


class PredictionRuntimeTests(unittest.TestCase):
    def test_build_estimated_recent_games_handles_non_numeric_values(self):
        row = {
            "player": "SyntheticUser",
            "uid": "local-001",
            "level": "not-a-number",
            "games_played": "unknown",
            "wins": "n/a",
            "kdr": "bad",
            "rank_score": None,
            "damage_per_game": "-",
        }

        recent_games = build_estimated_recent_games(
            row=row,
            rank_confidence=0.4,
            promotion_chance=0.3,
            demotion_risk=0.2,
        )

        self.assertEqual(len(recent_games), 5)
        for game in recent_games:
            self.assertIn("placement", game)
            self.assertIn("kills", game)
            self.assertIn("damage", game)
            self.assertIn("outcome", game)
            self.assertEqual(game.get("source"), "estimate")


if __name__ == "__main__":
    unittest.main()
