import unittest

from app.analytics import dashboard


def _trade(trade_id, session, pnl, r_multiple, tag_setup, plan=1):
    return {
        "id": trade_id,
        "is_closed": 1,
        "net_pnl": pnl,
        "r_multiple": r_multiple,
        "followed_plan": plan,
        "left_on_table": 0,
        "session": session,
        "kill_zone": session,
        "grade": "A+" if pnl > 0 else "C",
        "emotion_before": "Calm" if pnl > 0 else "Anxious",
        "setup": tag_setup,
        "instrument": "MES" if pnl > 0 else "NQ",
        "direction": "long" if pnl > 0 else "short",
        "closed_at": f"2026-10-{trade_id:02d}T12:00:00",
        "opened_at": f"2026-10-{trade_id:02d}T09:45:00",
    }


class AnalyticsTests(unittest.TestCase):
    def test_streaks_use_daily_net_and_skip_days_off(self):
        trades = []
        for index, (day, pnl) in enumerate(((1, 50), (1, -25), (2, 45), (5, 80),
                                            (5, -90), (6, -50), (7, 10), (7, -10), (8, 100)), start=1):
            trade = _trade(index, "NY AM", pnl, None, "")
            trade["closed_at"] = f"2026-10-{day:02d}T12:00:00"
            trades.append(trade)
        for count, wins, losses, current, kind in (
            (3, 2, 0, 2, "win"),
            (5, 2, 1, 1, "loss"),
            (6, 2, 2, 2, "loss"),
            (8, 2, 2, 0, None),
            (9, 2, 2, 1, "win"),
        ):
            with self.subTest(trades=count):
                self.assertEqual(dashboard(trades[:count], {})["streak"],
                                 {"win": wins, "loss": losses, "current": current, "kind": kind})

    def test_ny_am_fvg_sentence(self):
        trades = []
        tags = {}
        for index in range(1, 4):
            trades.append(_trade(index, "NY AM", 97.5, 1.8, "NY AM FVG"))
            tags[index] = ["FVG"]
        for index in range(4, 7):
            trades.append(_trade(index, "London", -42.0, -0.21, "", plan=0))
            tags[index] = []
        lines = dashboard(trades, tags)["insights"]
        self.assertTrue(any("NY AM FVG trades average" in line for line in lines), lines)
        self.assertTrue(any("London trades are down" in line for line in lines), lines)


if __name__ == "__main__":
    unittest.main()
