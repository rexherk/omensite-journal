import unittest
from datetime import datetime, date
from zoneinfo import ZoneInfo

from app.equity import TOPSTEP_EOD, TOPSTEP_STATIC, combine_rules, equity_chart, session_close

UTC = ZoneInfo("UTC")
NY = ZoneInfo("America/New_York")


def account(size=50000, profile=TOPSTEP_EOD, target=3000, loss=2000):
    return dict(id=7, name="Similar names do not determine rules", kind="prop",
                starting_balance=size, profit_target=target, trailing_drawdown=loss,
                consistency_pct=55, daily_loss_limit=1000, rule_profile=profile)


def trade(key, stamp, pnl, account_id=7):
    return dict(id=key, account_id=account_id, instrument="MES", is_closed=1,
                opened_at=stamp, closed_at=stamp, net_pnl=pnl)


class EquityTests(unittest.TestCase):
    def chart(self, trades, rules=None, **kwargs):
        return equity_chart(trades, {r["id"] for r in trades}, NY,
                            rules or account(), now=datetime(2026, 11, 14, tzinfo=UTC), **kwargs)

    def test_eod_limit_ignores_intraday_peak_never_falls_and_locks(self):
        rows = [
            trade(1, "2026-11-09T15:00:00Z", 1500),
            trade(2, "2026-11-09T16:00:00Z", -1000),
            trade(3, "2026-11-10T15:00:00Z", -400),
            trade(4, "2026-11-11T15:00:00Z", 2500),
            trade(5, "2026-11-12T15:00:00Z", -200),
        ]
        data = self.chart(rows)
        self.assertEqual([p["floor"] for p in data["points"]], [-2000, -2000, -1500, -1500, 0])
        settlements = {datetime.fromtimestamp(p["time"] / 1000, UTC).isoformat(): p
                       for p in data["limits"]}
        self.assertEqual(settlements["2026-11-09T21:10:00+00:00"]["floor"], -1500)
        self.assertEqual(settlements["2026-11-10T21:10:00+00:00"]["floor"], -1500)
        self.assertEqual(data["rules"]["current_balance_floor"], 50000)
        self.assertEqual([p["drawdown"] for p in data["points"]], [0, 1000, 1400, 0, 200])
        self.assertEqual(data["net_pnl"], 2400)
        self.assertEqual(data["rules"]["current_target"], 4545.46)

    def test_open_session_cannot_raise_eod_floor_early(self):
        rows = [trade(1, "2026-11-13T15:00:00Z", 500)]
        data = equity_chart(rows, {1}, NY, account(), now=datetime(2026,11,13,18,tzinfo=UTC))
        self.assertEqual(data["rules"]["current_floor"], -2000)
        self.assertTrue(all(p["floor"] == -2000 for p in data["limits"]))

    def test_static_plan_and_supported_sizes_have_distinct_targets(self):
        for size, target, loss in ((50000,3000,2000),(100000,6000,3000),(150000,9000,4500)):
            with self.subTest(size=size):
                rules, warning = combine_rules(account(size=size,target=target,loss=loss))
                self.assertIsNone(warning)
                self.assertEqual((rules["base_target"],rules["loss_amount"]), (target,loss))
        data = self.chart([trade(1,"2026-11-09T15:00:00Z",3000)],
                          account(profile=TOPSTEP_STATIC,target=4000))
        self.assertEqual(data["rules"]["current_floor"], -2000)
        self.assertFalse(data["rules"]["trailing"])
        self.assertEqual(data["rules"]["base_target"], 4000)

    def test_missing_or_mismatched_settings_never_infer_rules_from_names(self):
        for field, value in (("rule_profile",None),("starting_balance",0),("profit_target",None),
                             ("trailing_drawdown",3000),("consistency_pct",None)):
            with self.subTest(field=field):
                saved = account()
                saved["name"] = "Topstep 50K Combine #2"
                saved[field] = value
                rules, warning = combine_rules(saved)
                self.assertIsNone(rules)
                self.assertTrue(warning)
        data = equity_chart([trade(1,"2026-11-09T15:00:00Z",500)], {1}, NY)
        self.assertIsNone(data["rules"])
        self.assertEqual(data["limits"], [])

    def test_date_timezone_dst_session_rollover_and_range_baseline(self):
        rows = [trade(1,"2026-11-02T00:30:00Z",800), trade(2,"2026-11-03T01:00:00Z",-200)]
        data = equity_chart(rows,{2},ZoneInfo("America/Los_Angeles"),account(),
                            since=date(2026,11,2),now=datetime(2026,11,4,tzinfo=UTC))
        self.assertEqual(data["points"][0]["date"], "2026-11-02")
        self.assertEqual(data["points"][0]["net"], -200)
        self.assertEqual(data["points"][0]["drawdown"], 200)
        self.assertEqual(data["baseline"], 800)
        self.assertEqual(data["points"][0]["floor"], -1200)
        self.assertEqual(data["limits"][0]["floor"], -2000)
        self.assertEqual(data["limits"][0]["target"], 2200)
        self.assertEqual(session_close(datetime(2026,11,2,0,30,tzinfo=UTC)).astimezone(UTC),
                         datetime(2026,11,2,21,10,tzinfo=UTC))
        self.assertEqual(session_close(datetime(2026,10,29,23,30,tzinfo=UTC)).astimezone(UTC),
                         datetime(2026,10,30,20,10,tzinfo=UTC))

    def test_one_trade_and_no_trades(self):
        data = self.chart([trade(1,"2026-11-09T15:00:00Z",-20)])
        self.assertEqual(data["points"][0]["net"], -20)
        self.assertEqual(data["drawdown"], 20)
        empty = equity_chart([],set(),NY,account())
        self.assertEqual(empty["points"], [])
        self.assertEqual(empty["rules"]["base_target"], 3000)

    def test_account_identity_and_initial_drawdown_survive_a_shorter_range(self):
        rows = [trade(1,"2026-11-09T15:00:00Z",1000),
                trade(2,"2026-11-10T15:00:00Z",-600),
                trade(3,"2026-11-11T15:00:00Z",200),
                trade(4,"2026-11-11T16:00:00Z",9000,account_id=8)]
        data = equity_chart(rows,{3,4},NY,account(),since=date(2026,11,11),
                            now=datetime(2026,11,14,tzinfo=UTC))
        self.assertEqual([p["id"] for p in data["points"]],[3])
        self.assertEqual(data["baseline"],400)
        self.assertEqual(data["net_pnl"],200)
        self.assertEqual(data["initial_drawdown"],600)
        self.assertEqual(data["drawdown"],400)
        self.assertEqual(data["rules"]["current_floor"],-1000)
        self.assertEqual(data["rules"]["current_target"],3000)
