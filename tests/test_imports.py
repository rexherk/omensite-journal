import unittest
from zoneinfo import ZoneInfo

from app.imports import ImportError as CsvImportError
from app.imports import parse_csv

NY = ZoneInfo("America/New_York")


class ImportTests(unittest.TestCase):
    def test_round_trip_keeps_the_short_and_the_root(self):
        text = (
            "Symbol,Side,Qty,Entry Price,Exit Price,Entry Time,Exit Time\n"
            "MESZ6,Short,2,5000,5010,2026-10-01 09:45:00,2026-10-01 10:15:00\n"
        )
        rows = parse_csv(text, NY)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["instrument"], "MES")
        self.assertEqual(rows[0]["asset_class"], "future")
        self.assertEqual(rows[0]["direction"], "short")
        self.assertEqual([leg["kind"] for leg in rows[0]["legs"]], ["entry", "exit"])

    def test_fifo_short_stays_short(self):
        text = (
            "symbol,side,qty,price,time\n"
            "NQ,sell,1,20000,2026-10-01 03:20:00\n"
            "NQ,buy,1,20002,2026-10-01 04:00:00\n"
        )
        rows = parse_csv(text, NY)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["direction"], "short")
        self.assertEqual(rows[0]["instrument"], "NQ")

    def test_scale_in_is_one_trade(self):
        text = (
            "symbol,side,qty,price,time\n"
            "ES,buy,1,5000,2026-10-01 10:00:00\n"
            "ES,buy,1,5002,2026-10-01 10:05:00\n"
            "ES,sell,2,5010,2026-10-01 10:30:00\n"
        )
        rows = parse_csv(text, NY)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["direction"], "long")
        self.assertEqual(len(rows[0]["legs"]), 3)
        self.assertEqual(rows[0]["warnings"], [])

    def test_flip_leaves_the_new_side_open_and_keeps_the_fee_on_the_close(self):
        text = (
            "symbol,side,qty,price,time,fees\n"
            "ES,buy,2,5000,2026-10-01 10:00:00,1.25\n"
            "ES,sell,3,5010,2026-10-01 10:30:00,1.25\n"
        )
        rows = parse_csv(text, NY)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["direction"], "long")
        self.assertEqual(rows[0]["fees"], 2.5)
        self.assertEqual(rows[0]["legs"][1]["qty"], 2)
        self.assertEqual(rows[1]["direction"], "short")
        self.assertEqual(rows[1]["fees"], 0)
        self.assertEqual(rows[1]["legs"][0]["qty"], 1)
        self.assertIn("Still open when the file ended.", rows[1]["warnings"])

    def test_date_only_warns_exactly(self):
        text = "symbol,side,qty,price,time\nES,buy,1,5000,2026-10-01\n"
        rows = parse_csv(text, NY)
        self.assertEqual(rows[0]["warnings"].count("Time was missing, set to midnight."), 1)
        self.assertEqual(rows[0]["legs"][0]["filled_at"].hour, 0)

    def test_unrecognized_columns(self):
        with self.assertRaises(CsvImportError) as caught:
            parse_csv("foo,bar\n1,2\n", NY)
        self.assertIn("Unrecognized columns", str(caught.exception))

    def test_zulu_is_utc(self):
        text = "symbol,side,qty,price,time\nES,buy,1,5000,2026-10-01T14:00:00Z\n"
        rows = parse_csv(text, NY)
        self.assertEqual(rows[0]["legs"][0]["filled_at"].utcoffset().total_seconds(), 0)


if __name__ == "__main__":
    unittest.main()
