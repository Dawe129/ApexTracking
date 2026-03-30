import unittest

from src.predictor import ApexPredictor


class PredictorLogicTests(unittest.TestCase):
    def _new_predictor_without_model(self):
        predictor = ApexPredictor.__new__(ApexPredictor)
        predictor.win_rate_model = None
        return predictor

    def test_win_rate_fallback_stays_in_range(self):
        predictor = self._new_predictor_without_model()
        row = {
            "games_played": 300,
            "wins": 35,
            "kdr": 1.4,
            "rank_score": 8200,
        }

        value = predictor._estimate_win_rate_fallback(row)
        self.assertGreaterEqual(value, 0.0)
        self.assertLessEqual(value, 0.85)

    def test_recommendations_are_complete(self):
        predictor = self._new_predictor_without_model()
        row = {
            "kdr": 1.8,
            "damage_per_game": 950,
            "kills": 4500,
            "wins": 240,
            "headshots": 900,
            "rank_score": 14500,
            "games_played": 1500,
            "level": 350,
        }

        rec = predictor._recommendations(row)
        self.assertIn("best_map", rec)
        self.assertIn("best_legend", rec)
        self.assertIn("best_drop_zone", rec)
        self.assertIn("ideal_team_role", rec)
        self.assertIn("combat_style", rec)
        self.assertTrue(rec["best_map"])
        self.assertTrue(rec["best_legend"])


if __name__ == "__main__":
    unittest.main()
