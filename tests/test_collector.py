import unittest

from src.collector import _extract_recent_matches, player_to_row


class CollectorTests(unittest.TestCase):
    def test_extract_recent_matches_limits_and_normalizes(self):
        payload = {
            "matches": [
                {"placement": 1, "kills": 5, "damage": 1250},
                {"place": 3, "kill_count": 2, "damageDealt": 800},
                {"rank": 9, "kills": 1, "damage": 350},
                {"placement": 0, "kills": -2, "damage": -5},
                {"placement": 12, "kills": 0, "damage": 120},
                {"placement": 7, "kills": 1, "damage": 400},
            ]
        }

        recent = _extract_recent_matches(payload, limit=5)
        self.assertEqual(len(recent), 5)
        self.assertEqual(recent[0]["outcome"], "Win")
        self.assertEqual(recent[1]["outcome"], "Top 5")
        self.assertEqual(recent[2]["outcome"], "Mid/Late")
        self.assertEqual(recent[3]["placement"], 20)
        self.assertEqual(recent[3]["kills"], 0)
        self.assertEqual(recent[3]["damage"], 0.0)

    def test_player_to_row_adds_recent_matches(self):
        payload = {
            "global": {
                "name": "TestPlayer",
                "uid": "123",
                "level": 100,
                "rank": {"rankName": "Gold", "rankDiv": "2", "rankScore": 5000},
            },
            "total": {
                "kills": {"value": 200},
                "damage": {"value": 40000},
                "headshots": {"value": 120},
                "games_played": {"value": 100},
                "wins": {"value": 15},
                "kd": {"value": 2.0},
            },
            "matches": [
                {"placement": 4, "kills": 2, "damage": 700},
                {"placement": 1, "kills": 6, "damage": 1600},
            ],
        }

        row = player_to_row(payload, requested_name="Fallback")
        self.assertEqual(row["player"], "TestPlayer")
        self.assertEqual(row["uid"], "123")
        self.assertIn("recent_matches", row)
        self.assertEqual(len(row["recent_matches"]), 2)
        self.assertEqual(row["recent_matches"][1]["outcome"], "Win")


if __name__ == "__main__":
    unittest.main()
