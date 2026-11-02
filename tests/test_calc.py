import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from app.calc import Leg, TradeMathError, grade_for, kill_zone_for, macro_for, session_for, summarize

NY = ZoneInfo("America/New_York")


def _at(hour: int, minute: int) -> datetime:
    return datetime(2026, 10, 21, hour, minute, tzinfo=NY)


class CalcTests(unittest.TestCase):
    def test_long_es_round_trip(self):
        stats = summarize(
            direction="long",
            legs=[
                Leg("entry", 1, 5000, _at(10, 0)),
                Leg("exit", 1, 5010, _at(10, 30)),
            ],
            stop=4990,
            target=5020,
            fees=0,
            point_value=50,
            tick=0.25,
            mae_price=None,
            mfe_price=None,
        )
        self.assertEqual(stats.net_pnl, 500.0)
        self.assertEqual(stats.r_multiple, 1.0)
        self.assertTrue(stats.is_closed)
        self.assertEqual(stats.session, "NY AM")
        self.assertEqual(stats.kill_zone, "NY AM Silver Bullet")

    def test_fees_come_out_of_the_net(self):
        stats = summarize(
            direction="long",
            legs=[
                Leg("entry", 1, 5000, _at(10, 0)),
                Leg("exit", 1, 5010, _at(10, 30)),
            ],
            stop=4990,
            target=None,
            fees=4.50,
            point_value=50,
            tick=0.25,
            mae_price=None,
            mfe_price=None,
        )
        self.assertEqual(stats.gross_pnl, 500.0)
        self.assertEqual(stats.net_pnl, 495.50)

    def test_long_partial_stays_open(self):
        stats = summarize(
            direction="long",
            legs=[
                Leg("entry", 2, 5800, _at(11, 0)),
                Leg("exit", 1, 5810, _at(11, 20)),
            ],
            stop=None,
            target=None,
            fees=0,
            point_value=5,
            tick=0.25,
            mae_price=None,
            mfe_price=None,
        )
        self.assertEqual(stats.gross_pnl, 50.0)
        self.assertEqual(stats.open_qty, 1)
        self.assertFalse(stats.is_closed)
        self.assertIsNone(stats.closed_at)

    def test_short_profit(self):
        stats = summarize(
            direction="short",
            legs=[
                Leg("entry", 1, 20000, _at(3, 20)),
                Leg("exit", 1, 19990, _at(4, 0)),
            ],
            stop=20010,
            target=19980,
            fees=0,
            point_value=20,
            tick=0.25,
            mae_price=20005,
            mfe_price=19990,
        )
        self.assertEqual(stats.gross_pnl, 200.0)
        self.assertEqual(stats.r_multiple, 1.0)
        self.assertEqual(stats.session, "London")
        self.assertEqual(stats.kill_zone, "London Silver Bullet")
        self.assertGreater(stats.mae_points, 0)
        self.assertGreater(stats.mfe_points, 0)

    def test_exit_larger_than_open_size(self):
        with self.assertRaises(TradeMathError):
            summarize(
                direction="long",
                legs=[
                    Leg("entry", 1, 5000, _at(10, 0)),
                    Leg("exit", 2, 5010, _at(10, 5)),
                ],
                stop=None,
                target=None,
                fees=0,
                point_value=50,
                tick=0.25,
                mae_price=None,
                mfe_price=None,
            )

    def test_grade_thresholds(self):
        self.assertEqual(grade_for(10, 10), "A+")
        self.assertEqual(grade_for(8, 10), "A")
        self.assertEqual(grade_for(6, 10), "B")
        self.assertEqual(grade_for(5, 10), "C")
        self.assertIsNone(grade_for(0, 0))

    def test_new_york_clocks(self):
        self.assertEqual(session_for(_at(10, 0)), "NY AM")
        self.assertEqual(kill_zone_for(_at(10, 0)), "NY AM Silver Bullet")
        self.assertEqual(macro_for(_at(9, 50)), "09:50-10:10")
        self.assertEqual(session_for(_at(3, 30)), "London")
        self.assertEqual(kill_zone_for(_at(3, 30)), "London Silver Bullet")
        self.assertEqual(session_for(_at(9, 0)), "NY AM")
        self.assertEqual(kill_zone_for(_at(9, 0)), "NY AM")
        self.assertEqual(session_for(_at(19, 30)), "Asia")
        self.assertEqual(kill_zone_for(_at(19, 30)), "None")

    def test_blank_session_uses_the_clock_and_the_word_none_is_kept(self):
        kept = summarize(
            direction="long",
            legs=[Leg("entry", 1, 5000, _at(10, 0))],
            stop=None,
            target=None,
            fees=0,
            point_value=50,
            tick=0.25,
            mae_price=None,
            mfe_price=None,
            session="None",
        )
        self.assertEqual(kept.session, "None")
        auto = summarize(
            direction="long",
            legs=[Leg("entry", 1, 5000, _at(10, 0))],
            stop=None,
            target=None,
            fees=0,
            point_value=50,
            tick=0.25,
            mae_price=None,
            mfe_price=None,
            session=None,
        )
        self.assertEqual(auto.session, "NY AM")


if __name__ == "__main__":
    unittest.main()
