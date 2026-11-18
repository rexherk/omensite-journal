import os
import hashlib
import re
import tempfile
import unittest
from datetime import date, datetime
from unittest.mock import patch

os.environ["OMENSITE_DATA"] = tempfile.mkdtemp(prefix="omensite-journal-")

from fastapi.testclient import TestClient

from app.main import app

PNG = bytes.fromhex(
    "89504E470D0A1A0A0000000D49484452000000010000000108060000001F15C489"
    "0000000A49444154789C63000100000500010D0A2DB40000000049454E44AE426082"
)


def csrf_from(html: str) -> str:
    for marker in ('name="csrf" value="', 'name="csrf" content="'):
        if marker in html:
            return html.split(marker, 1)[1].split('"', 1)[0]
    raise AssertionError("No CSRF token on the page.")


def account_from(html: str) -> str:
    match = re.search(r'name="account_id".*?<option value="(\d+)"', html, re.S)
    if not match:
        raise AssertionError("No account on the trade form.")
    return match.group(1)


class AppTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app, follow_redirects=True)
        cls.client.__enter__()
        cls.email = "trader@example.com"
        cls.client.cookies.clear()
        cls.session = cls.fixture_session(cls.email)

    @staticmethod
    def fixture_session(email: str) -> str:
        from app import db
        from app.services import login_discord, start_session
        discord_id = str(int.from_bytes(hashlib.sha256(email.encode()).digest()[:8], "big"))
        with db.session() as conn:
            user_id = login_discord(conn, {"id": discord_id, "username": email.split("@")[0], "email": email, "verified": True})
            db.set_onboarded(conn, user_id, 1)
            return start_session(conn, user_id)

    @classmethod
    def tearDownClass(cls):
        cls.client.__exit__(None, None, None)

    def setUp(self):
        self.client.cookies.clear()
        self.client.cookies.set("omensite_session", self.session)
        home = self.client.get("/")
        self.assertEqual(home.status_code, 200)
        self.assertIn("Sign out", home.text)
        self.csrf = csrf_from(home.text)
        form = self.client.get("/trades/new")
        self.account = account_from(form.text)

    def sign_in_as(self, email: str) -> str:
        self.client.cookies.clear()
        self.client.cookies.set("omensite_session", self.fixture_session(email))
        page = self.client.get("/")
        self.assertEqual(page.status_code, 200)
        self.assertIn("Sign out", page.text)
        return csrf_from(page.text)

    def post_trade(self, **fields):
        legs = fields["legs"]
        data = {
            "csrf": self.csrf,
            "instrument": fields.get("instrument", "ES"),
            "asset_class": fields.get("asset_class", "future"),
            "direction": fields.get("direction", "long"),
            "account_id": self.account,
            "fees": fields.get("fees", "0"),
            "stop": fields.get("stop", ""),
            "target": fields.get("target", ""),
            "leg_kind": [leg[0] for leg in legs],
            "leg_qty": [leg[1] for leg in legs],
            "leg_price": [leg[2] for leg in legs],
            "leg_time": [leg[3] for leg in legs],
        }
        page = self.client.post("/trades", data=data)
        self.assertEqual(page.status_code, 200, page.text[:800])
        self.assertNotIn("Each fill", page.text)
        return page

    def test_health_and_login_copy(self):
        self.assertEqual(self.client.get("/health").json(), {"ok": True, "name": "Omensite Journal"})
        self.client.cookies.clear()
        home = self.client.get("/")
        self.assertEqual(home.url.path, "/login")
        self.assertIn("Log in to your journal", home.text)
        self.assertIn('href="/demo"', home.text)
        login = self.client.get("/login")
        self.assertIn('href="/auth/discord"', login.text)
        self.assertNotIn('name="email"', login.text)
        self.assertNotIn('name="password"', login.text)
        self.assertEqual(self.client.cookies.get("omensite_csrf"), csrf_from(login.text))

    def test_pages_render(self):
        for path in (
            "/",
            "/trades",
            "/trades/new",
            "/import",
            "/news",
            "/plan",
            "/reviews",
            "/playbook",
            "/report",
            "/settings",
        ):
            page = self.client.get(path)
            self.assertEqual(page.status_code, 200, path)
            self.assertIn("Omensite Journal", page.text)
        news = self.client.get("/news")
        self.assertIn('title="Tradays economic calendar"', news.text)
        self.assertIn("NYSE market dates", news.text)
        self.assertIn("noindex", news.text)

    def test_intro_and_dashboard_shell(self):
        self.client.cookies.clear()
        intro = self.client.get("/home")
        self.assertIn('href="/signup"', intro.text)
        self.assertIn('href="/demo"', intro.text)
        self.assertIn('role="tablist"', intro.text)
        self.assertIn("/static/js/landing.js", intro.text)
        self.assertIn("Sign in with Discord to create your journal.", intro.text)
        self.assertNotIn("Get Access", intro.text)
        self.assertNotIn("Sign out", intro.text)
        self.client.cookies.set("omensite_session", self.session)
        desk = self.client.get("/")
        self.assertIn("<h1>Dashboard</h1>", desk.text)
        self.assertIn("Equity", desk.text)
        self.assertIn("Daily P&amp;L", desk.text)
        self.assertIn("What the journal sees", desk.text)
        self.assertIn("/static/css/brand.css", desk.text)
        self.assertIn("/static/css/journal-brand.css", desk.text)
        self.assertNotIn("hero-title", desk.text)

    def test_public_navigation_pages_and_topstep_support(self):
        self.client.cookies.clear()
        paths = ["/home", "/signup", "/login", "/forgot", "/reset/example", "/products", "/solutions", "/brokers", "/resources", "/privacy"]
        paths += ["/products/" + key for key in ("journal", "analytics", "reviews", "playbook", "plan", "prop")]
        paths += ["/solutions/" + key for key in ("consistency", "performance", "funded")]
        paths += ["/resources/" + key for key in ("getting-started", "review-routine", "faq")]
        for path in paths:
            page = self.client.get(path)
            self.assertEqual(page.status_code, 200, path)
            self.assertIn("/static/css/brand.css", page.text, path)
            self.assertIn('href="/products"', page.text, path)
            self.assertNotIn("Get Access", page.text, path)
        for path in ("/home", "/brokers", "/resources/faq"):
            page = self.client.get(path)
            self.assertIn("Topstep", page.text)
            for broker in ("Tradovate", "NinjaTrader", "Webull", "Robinhood"):
                self.assertNotIn(broker, page.text)
        self.assertEqual(self.client.get("/products/missing").status_code, 404)

    def test_discord_signup_creates_an_account_and_onboards(self):
        self.client.cookies.clear()
        self.client.get("/demo")
        for path in ("/signup", "/login", "/register"):
            page = self.client.get(path)
            self.assertEqual(page.status_code, 200)
            self.assertEqual(page.text.count('class="discord-button discord-only-button"'), 1)
            self.assertIn('href="/auth/discord"', page.text)
            self.assertNotIn('name="email"', page.text)
            self.assertNotIn('name="password"', page.text)
            self.assertNotIn('action="/register"', page.text)
            self.assertNotIn('href="/forgot"', page.text)
        profile = {"id": "987654321098765432", "username": "prospect", "global_name": "New Trader", "email": "prospect@example.com", "verified": True}
        with patch("app.main.authorize_url", return_value=("https://discord.com/oauth2/authorize?state=discord-test-state", "discord-test-state")), patch("app.main.fetch_profile", return_value=profile):
            authorize = self.client.get("/auth/discord", follow_redirects=False)
            self.assertEqual(authorize.status_code, 303)
            self.assertIn("discord.com/oauth2/authorize", authorize.headers["location"])
            created = self.client.get("/auth/discord/callback?code=test-code&state=discord-test-state")
        self.assertEqual(created.status_code, 200)
        self.assertIn("Three steps, then the dashboard.", created.text)
        self.assertIn("Topstep", created.text)
        self.assertNotIn("Apex", created.text)
        self.assertIsNone(self.client.cookies.get("omensite_demo"))
        self.assertNotIn("Demo workspace", created.text)
        self.assertTrue(self.client.cookies.get("omensite_session"))

    def test_alternative_authentication_endpoints_are_disabled(self):
        self.client.cookies.clear()
        for path in ("/login", "/register", "/forgot", "/reset/legacy-token"):
            response = self.client.post(path, data={"email": "trader@example.com", "password": "ignored"})
            self.assertEqual(response.status_code, 405, path)
        for path in ("/auth/google", "/auth/google/callback"):
            self.assertEqual(self.client.get(path).status_code, 404, path)
        for path in ("/forgot", "/reset/legacy-token"):
            response = self.client.get(path, follow_redirects=False)
            self.assertEqual(response.status_code, 303, path)
            self.assertEqual(response.headers["location"], "/login")

    def test_demo_is_read_only_and_preserves_real_session(self):
        personal_before = self.client.get("/export.json").json()
        demo = self.client.get("/demo")
        self.assertEqual(demo.status_code, 200)
        self.assertIn("Demo workspace", demo.text)
        self.assertIn("Sample data", demo.text)
        self.assertIn("Topstep 50K Combine #XXXX226", demo.text)
        self.assertEqual(self.client.cookies.get("omensite_session"), self.session)
        self.assertTrue(self.client.cookies.get("omensite_demo"))
        token = csrf_from(demo.text)
        demo_session = self.client.cookies.get("omensite_demo")
        for path in ("/trades", "/settings/profile", "/settings/sample", "/import/confirm", "/plan", "/playbook"):
            blocked = self.client.post(path, data={"csrf": token, "timezone": "UTC"})
            self.assertEqual(blocked.status_code, 403, path)
            self.assertIn("This demo is read-only.", blocked.text)
        for path in ("/trades", "/reviews", "/playbook", "/plan", "/report", "/settings", "/import"):
            self.assertEqual(self.client.get(path).status_code, 200, path)
        self.assertEqual(self.client.get("/signup").status_code, 200)
        self.client.get("/demo/exit")
        self.assertIsNone(self.client.cookies.get("omensite_demo"))
        self.assertEqual(self.client.cookies.get("omensite_session"), self.session)
        personal_after = self.client.get("/export.json").json()
        personal_before.pop("exported_at", None)
        personal_after.pop("exported_at", None)
        self.assertEqual(personal_after, personal_before)
        self.assertNotIn("Demo workspace", self.client.get("/").text)
        self.client.cookies.clear()
        self.client.cookies.set("omensite_session", demo_session, domain="testserver.local", path="/")
        self.client.get("/demo/exit")
        self.assertIsNone(self.client.cookies.get("omensite_session"))

    def test_homepage_and_demo_use_the_same_calculated_sample(self):
        from app.sample_data import sample_through, sample_trades

        self.client.cookies.clear()
        through = sample_through()
        with patch("app.main.sample_through", return_value=through):
            home = self.client.get("/home")
            demo = self.client.get("/demo")
        for attribute in ("data-net-pnl", "data-month-pnl"):
            pattern = attribute + r'="([^"]+)"'
            self.assertEqual(re.findall(pattern, home.text), re.findall(pattern, demo.text))
        pattern = r'data-date="([^"]+)" data-pnl="([^"]+)" data-trades="([^"]+)"'
        home_days = re.findall(pattern, home.text)
        self.assertEqual(home_days, re.findall(pattern, demo.text))
        self.assertGreaterEqual(sum(count == "0" for _, _, count in home_days), 2)
        net = float(re.search(r'data-net-pnl="([^"]+)"', demo.text).group(1))
        month_net = float(re.search(r'data-month-pnl="([^"]+)"', demo.text).group(1))
        self.assertAlmostEqual(sum(float(pnl) for _, pnl, _ in home_days), month_net, places=2)
        self.assertAlmostEqual(sum(trade["net_pnl"] for trade in sample_trades(through)), net, places=2)
        prop_equity = re.search(r'Account equity</small><strong>([^<]+)', home.text).group(1)
        self.assertIn(f"Final balance</span><strong>{prop_equity}</strong>", demo.text)

        for month, count, pnl in (("2026-07", 7, 1993.50), ("2026-08", 35, -2995.00),
                                  ("2026-09", 12, 83.50), ("2026-10", 51, 7758.00)):
            with self.subTest(month=month):
                response = self.client.get("/", params={"month": month})
                days = re.findall(pattern, response.text)
                self.assertEqual(sum(int(n) for _, _, n in days), count)
                self.assertAlmostEqual(sum(float(value) for _, value, _ in days), pnl, places=2)
                self.assertTrue(any(date.fromisoformat(day).weekday() < 5 and n == "0" for day, _, n in days))
                self.assertTrue(all(date.fromisoformat(day).weekday() < 5 for day, _, n in days if n != "0"))

    def test_all_demo_r_values_match_fills_and_initial_stop_risk(self):
        from app.instruments import FUTURES

        self.client.get("/demo").raise_for_status()
        backup = self.client.get("/export/backup").json()
        self.assertGreater(len(backup["trades"]), 100)
        for trade in backup["trades"]:
            with self.subTest(opened=trade["opened_local"], instrument=trade["instrument"]):
                entries = [leg for leg in trade["legs"] if leg["kind"] == "entry"]
                exits = [leg for leg in trade["legs"] if leg["kind"] == "exit"]
                quantity = sum(leg["qty"] for leg in entries)
                self.assertEqual(quantity, sum(leg["qty"] for leg in exits))
                entry_value = sum(leg["price"] * leg["qty"] for leg in entries)
                exit_value = sum(leg["price"] * leg["qty"] for leg in exits)
                spec = FUTURES[trade["instrument"]]
                point_value = spec.point_value
                sign = 1 if trade["direction"] == "long" else -1
                gross = (exit_value - entry_value) * point_value * sign
                net = gross - trade["fees"]
                entry = entry_value / quantity
                stop_points = (entry - trade["stop"]) * sign
                target_points = (trade["target"] - entry) * sign
                risk = stop_points * quantity * point_value
                self.assertGreater(risk, 0)
                self.assertEqual(target_points, 2 * stop_points)
                self.assertEqual(trade["planned_r"], 2.0)
                self.assertEqual(trade["stop"] % spec.tick, 0)
                self.assertEqual(trade["target"] % spec.tick, 0)
                if trade["instrument"] in {"MNQ", "MES"}:
                    self.assertGreaterEqual(stop_points, 20)
                    self.assertLessEqual(stop_points, 30)
                self.assertAlmostEqual(trade["gross_pnl"], gross, places=2)
                self.assertAlmostEqual(trade["net_pnl"], net, places=2)
                self.assertAlmostEqual(trade["risk_dollars"], risk, places=2)
                self.assertAlmostEqual(trade["r_multiple"], net / risk, places=4)

    def test_existing_demo_trade_plans_backfill_in_place(self):
        from app import db
        from app.sample_data import DEMO_EMAIL, DEMO_NOTE, sample_through

        plan_fields = {"stop", "target", "risk_dollars", "planned_r", "r_multiple"}

        def fill_history(conn, user_id):
            return {trade["id"]: (
                {key: value for key, value in trade.items() if key not in plan_fields},
                db.legs(conn, trade["id"]),
            ) for trade in db.trades(conn, user_id)}

        through = sample_through()
        with patch("app.main.sample_through", return_value=through):
            self.client.get("/demo").raise_for_status()
            with db.session() as conn:
                user_id = db.user_by_email(conn, DEMO_EMAIL)["id"]
                conn.execute(
                    "UPDATE trades SET target = NULL, planned_r = NULL WHERE user_id = ? AND notes = ?",
                    (user_id, DEMO_NOTE),
                )
                history = fill_history(conn, user_id)
                trade_id = next(iter(history))

            # A visitor with an existing demo cookie sees the backfill even at the same cutoff.
            page = self.client.get(f"/trades/{trade_id}")
            self.assertEqual(page.status_code, 200)
            self.assertIn("<dt>Planned R:R</dt><dd>2:1</dd>", page.text)
            self.assertNotIn("<dt>Left on table</dt>", page.text)
            with db.session() as conn:
                self.assertEqual(fill_history(conn, user_id), history)
                self.assertTrue(all(t["planned_r"] == 2.0 for t in db.trades(conn, user_id)))

    def test_existing_demo_session_backfills_ict_context_without_replacing_fills(self):
        from app import db
        from app.sample_data import DEMO_EMAIL, sample_through

        with patch("app.main.sample_through", return_value=sample_through()):
            self.client.get("/demo").raise_for_status()
            with db.session() as conn:
                user_id = db.user_by_email(conn, DEMO_EMAIL)["id"]
                trade = next(row for row in db.trades(conn, user_id)
                             if row["setup"] == "Liquidity sweep" and row["direction"] == "short")
                trade_id = trade["id"]
                legs = db.legs(conn, trade_id)
                conn.execute("UPDATE trades SET htf_bias = '', draw = '', lesson = '' WHERE id = ?", (trade_id,))
                conn.execute("DELETE FROM trade_tags WHERE trade_id = ?", (trade_id,))

            for _ in range(2):
                page = self.client.get(f"/trades/{trade_id}")
                self.assertEqual(page.status_code, 200)
                self.assertIn("<dt>Entry time</dt><dd><time", page.text)
                self.assertIn("<dt>Exit time</dt><dd><time", page.text)
                self.assertNotIn("<dt>Average entry</dt>", page.text)
                self.assertNotIn("<dt>Average exit</dt>", page.text)
                self.assertNotIn("review-chart-fills", page.text)
                self.assertIn("Simulated setup.", page.text)
                self.assertIn("Buy-side liquidity sweep", page.text)
            with db.session() as conn:
                self.assertEqual(db.trade(conn, user_id, trade_id), trade)
                self.assertEqual(db.legs(conn, trade_id), legs)
                self.assertCountEqual(db.tags_for_user(conn, user_id)[trade_id],
                                      ["Buy-side liquidity sweep", "MSS", "FVG"])

    def test_topstep_demo_challenge_migrates_and_passes(self):
        from collections import defaultdict
        from app import db
        from app.sample_data import (
            CHALLENGE_END, DEMO_EMAIL, DEMO_NOTE, DEMO_PROP, FORMER_DEMO_PROP_NAMES, LEGACY_DEMO_PROP,
        )

        self.client.get("/demo").raise_for_status()
        with db.session() as conn:
            user_id = db.user_by_email(conn, DEMO_EMAIL)["id"]
            account_id = next(row["id"] for row in db.accounts(conn, user_id) if row["name"] == DEMO_PROP["name"])
            existing_ids = {row["id"] for row in db.trades(conn, user_id)}
            conn.execute("UPDATE accounts SET name = ?, profit_target = 6000 WHERE id = ?",
                         (LEGACY_DEMO_PROP, account_id))
            conn.execute("UPDATE trades SET account_id = ? WHERE user_id = ? AND notes = ?",
                         (account_id, user_id, DEMO_NOTE))

        # Old range links still show the completed Combine's full history.
        demo = self.client.get("/", params={"range": "mtd", "account": account_id})
        self.assertEqual(demo.status_code, 200)
        self.assertIn("Topstep 50K Combine #XXXX226", demo.text)
        self.assertRegex(demo.text, r'Account XXXX\d{3}</p>')
        self.assertNotIn("Simulated Trading Combine", demo.text)
        self.assertIn('title="Passed Oct 13, 2026"', demo.text)
        self.assertIn("$53,135.00", demo.text)

        with db.session() as conn:
            rows = db.trades(conn, user_id)
            self.assertEqual({row["id"] for row in rows}, existing_ids)
            self.assertEqual(db.account(conn, user_id, account_id)["consistency_pct"], 55)
        challenge = [row for row in rows if row["account_id"] == account_id]
        self.assertEqual(len(challenge), 20)
        by_day = defaultdict(list)
        for row in sorted(challenge, key=lambda row: row["closed_local"]):
            by_day[row["closed_local"][:10]].append(row["net_pnl"])
        self.assertEqual(max(by_day), CHALLENGE_END.isoformat())
        balance = 0
        floor = -DEMO_PROP["trailing_drawdown"]
        for day, amounts in sorted(by_day.items()):
            for pnl in amounts:
                balance += pnl
                self.assertGreater(balance, floor)
            floor = min(0, max(floor, balance - DEMO_PROP["trailing_drawdown"]))
            if day < CHALLENGE_END.isoformat():
                self.assertLess(balance, DEMO_PROP["profit_target"])
        self.assertEqual(balance, 3135)
        self.assertLessEqual(max(map(sum, by_day.values())) / balance, DEMO_PROP["consistency_pct"] / 100)
        previous_name = FORMER_DEMO_PROP_NAMES[1]
        with db.session() as conn:
            conn.execute("UPDATE accounts SET name = ? WHERE user_id = ? AND id = ?",
                         (previous_name, user_id, account_id))
        renamed = self.client.get("/")
        self.assertIn(DEMO_PROP["name"], renamed.text)
        self.assertNotIn(previous_name, renamed.text)
        with db.session() as conn:
            self.assertEqual(db.account(conn, user_id, account_id)["name"], DEMO_PROP["name"])
            self.assertEqual({row["id"]: row["account_id"] for row in db.trades(conn, user_id)},
                             {row["id"]: row["account_id"] for row in rows})

    def test_demo_updates_an_existing_session_without_replacing_trade_ids(self):
        from app import db
        from app.sample_data import DEMO_EMAIL, DEMO_NOTE, NY, sample_through

        def trade_ids(note):
            with db.session() as conn:
                user = db.user_by_email(conn, DEMO_EMAIL)
                return {row["id"] for row in db.trades(conn, user["id"]) if row["notes"] == note}

        before = sample_through(datetime(2026, 11, 3, 12, 59, tzinfo=NY))
        after = sample_through(datetime(2026, 11, 3, 13, 0, tzinfo=NY))
        self.assertEqual(before, date(2026, 11, 2))
        self.assertEqual(after, date(2026, 11, 3))
        with tempfile.TemporaryDirectory() as data, patch.dict(os.environ, {"OMENSITE_DATA": data}), TestClient(app) as demo:
            with patch("app.main.sample_through", return_value=before):
                self.assertEqual(demo.get("/demo").status_code, 200)
                legacy_note = "Omensite demo v3 2026-10"
                with db.session() as conn:
                    conn.execute("UPDATE trades SET notes = ? WHERE notes = ?", (legacy_note, DEMO_NOTE))
                self.assertTrue(trade_ids(legacy_note))
                self.assertEqual(demo.get("/").status_code, 200)
                self.assertEqual(trade_ids(legacy_note), set())
                previous_ids = trade_ids(DEMO_NOTE)
                self.assertTrue(previous_ids)
            with patch("app.main.sample_through", return_value=after):
                self.assertEqual(demo.get("/trades").status_code, 200)
                new_ids = trade_ids(DEMO_NOTE)
                self.assertTrue(previous_ids < new_ids)
                self.assertEqual(demo.get("/demo").status_code, 200)
                self.assertEqual(trade_ids(DEMO_NOTE), new_ids)

    def test_second_demo_combine_preserves_and_filters_account_history(self):
        from app import db
        from app.sample_data import DEMO_EMAIL, DEMO_FUNDED_NAME, DEMO_PROP, DEMO_SECOND_COMBINE, SECOND_COMBINE_START

        with tempfile.TemporaryDirectory() as data, patch.dict(os.environ, {"OMENSITE_DATA": data}), TestClient(app) as demo:
            with patch("app.main.sample_through", return_value=SECOND_COMBINE_START):
                demo.get("/demo").raise_for_status()
                with db.session() as conn:
                    user_id = db.user_by_email(conn, DEMO_EMAIL)["id"]
                    accounts = {a["name"]: a["id"] for a in db.accounts(conn, user_id)}
                    original_id = accounts[DEMO_PROP["name"]]
                    rows = db.trades(conn, user_id)
                    launch = [row for row in rows if row["closed_day"] == SECOND_COMBINE_START.isoformat()]
                    self.assertEqual(len(launch), 4)
                    self.assertTrue(all(row["account_id"] == accounts[DEMO_SECOND_COMBINE] for row in launch))

                    # Recreate the old release's state after its launch-day refresh.
                    conn.execute("UPDATE trades SET account_id = ? WHERE user_id = ? AND account_id = ?",
                                 (accounts["Personal"], user_id, accounts[DEMO_SECOND_COMBINE]))
                    db.delete_account(conn, user_id, accounts[DEMO_SECOND_COMBINE])

                previous = demo.get("/", params={"account": original_id, "range": "all"}).raise_for_status().text
                self.assertIn("Passed Oct 13, 2026", previous)
                self.assertIn('data-net-pnl="3135.0"', previous)
                self.assertIn(f'/trades?account={original_id}">View trade history', previous)
                self.assertIn(f'>{DEMO_SECOND_COMBINE}</option>', previous)
                self.assertEqual(demo.get("/trades", params={"account": original_id}).text.count(
                    'class="button ghost trade-view"'), 20)

                with db.session() as conn:
                    accounts = {a["name"]: a["id"] for a in db.accounts(conn, user_id)}
                    restored = db.trades(conn, user_id)
                self.assertEqual([row["id"] for row in restored], [row["id"] for row in rows])
                self.assertEqual([row["net_pnl"] for row in restored], [row["net_pnl"] for row in rows])
                self.assertFalse(any(row["account_id"] == accounts[DEMO_FUNDED_NAME] for row in restored))
                second_id = accounts[DEMO_SECOND_COMBINE]
                self.assertEqual({row["id"] for row in restored if row["account_id"] == second_id},
                                 {row["id"] for row in launch})
                current = demo.get("/", params={"account": second_id}).raise_for_status().text
                self.assertIn('data-net-pnl="1869.5"', current)
                self.assertIn("In progress", current)

            with patch("app.main.sample_through", return_value=date(2026, 11, 10)):
                demo.get("/trades").raise_for_status()
                with db.session() as conn:
                    new_rows = [row for row in db.trades(conn, user_id) if row["closed_day"] == "2026-11-10"]
                self.assertEqual([row["account_id"] for row in new_rows], [second_id])

    def test_demo_combine_number_names_preserve_accounts_and_trades(self):
        from app import db
        from app.sample_data import DEMO_EMAIL, DEMO_COMBINE_RENAMES

        with tempfile.TemporaryDirectory() as data, patch.dict(os.environ, {"OMENSITE_DATA": data}), TestClient(app) as demo:
            with patch("app.main.sample_through", return_value=date(2026, 11, 13)):
                demo.get("/demo").raise_for_status()
                with db.session() as conn:
                    user_id = db.user_by_email(conn, DEMO_EMAIL)["id"]
                    accounts = db.accounts(conn, user_id)
                    ids = {a["name"]: a["id"] for a in accounts}
                    trades = db.many(conn, "SELECT * FROM trades WHERE user_id = ? ORDER BY id", (user_id,))
                    fills = {t["id"]: db.legs(conn, t["id"]) for t in trades}
                    for old_name, name in DEMO_COMBINE_RENAMES.items():
                        conn.execute("UPDATE accounts SET name = ? WHERE user_id = ? AND id = ?",
                                     (old_name, user_id, ids[name]))

                # An existing session migrates both names in place, and reopening is idempotent.
                demo.get("/").raise_for_status()
                demo.get("/demo").raise_for_status()
                with db.session() as conn:
                    self.assertEqual(db.accounts(conn, user_id), accounts)
                    self.assertEqual(db.many(conn, "SELECT * FROM trades WHERE user_id = ? ORDER BY id", (user_id,)), trades)
                    self.assertEqual({t["id"]: db.legs(conn, t["id"]) for t in trades}, fills)

                for old_name, name in DEMO_COMBINE_RENAMES.items():
                    home = demo.get("/", params={"account": ids[name]}).raise_for_status().text
                    self.assertIn(f'>{name}</option>', home)
                    self.assertIn(f'>{name}</h3>', home)
                    self.assertNotIn(f'>{old_name}</', home)
                    history = demo.get("/trades", params={"account": ids[name]}).raise_for_status().text
                    self.assertIn(name, history)
                    trade_id = next(t["id"] for t in trades if t["account_id"] == ids[name])
                    self.assertIn(name, demo.get(f"/trades/{trade_id}").raise_for_status().text)
                exported = demo.get("/export/backup").raise_for_status().json()
                self.assertEqual({a["name"] for a in exported["accounts"]}, set(ids))

    def test_demo_review_chart_uses_saved_fills_and_preserves_history(self):
        from app import db
        from app.sample_data import DEMO_EMAIL

        self.client.get("/demo").raise_for_status()
        before = self.client.get("/export/backup").json()["trades"]
        with db.session() as conn:
            user = db.user_by_email(conn, DEMO_EMAIL)
            trades = db.trades(conn, user["id"])
            earliest = min(trades, key=lambda trade: trade["opened_at"])
        for trade in (trades[0], earliest):
            page = self.client.get(f'/trades/{trade["id"]}').raise_for_status().text
            self.assertIn('class="sample-fill-chart"', page)
            self.assertIn("Two recorded sample fills", page)
            self.assertIn("Setup rationale", page)
            self.assertIn("Execution outcome", page)
            self.assertIn("Review focus", page)
            self.assertNotIn(">Edit trade</a>", page)
            self.assertNotIn("No trade chart yet", page)
        self.assertEqual(self.client.get("/export/backup").json()["trades"], before)

    def test_reviews_are_monthly_and_expand_trade_groups(self):
        self.client.get("/demo").raise_for_status()
        month = self.client.get("/reviews?period=month&month=2026-10").raise_for_status().text
        self.assertIn("October 2026", month)
        self.assertIn("$7,758.00", month)
        self.assertIn('<details class="journal-disclosure">', month)
        self.assertIn('data-auto-submit', month)
        self.assertIn('name="month" value="2026-10"', month)
        self.assertNotIn('name="week"', month)
        self.assertNotIn('Apply date', month)
        self.assertNotIn('>Week</a>', month)
        legacy = self.client.get("/reviews?period=week&week=invalid&month=2026-10").raise_for_status().text
        self.assertIn("October 2026", legacy)
        self.assertIn("$7,758.00", legacy)
        empty = self.client.get("/reviews?period=month&month=2026-01").raise_for_status().text
        self.assertIn("No trades closed in this month", empty)
        self.assertNotIn('<details class="journal-disclosure">', empty)
        self.assertEqual(self.client.get("/reviews?month=invalid").status_code, 400)

    def test_report_is_monthly_only_and_print_follows_trades(self):
        self.client.get("/demo").raise_for_status()
        before = self.client.get("/export/backup").json()["trades"]
        july = self.client.get("/report?month=2026-07").raise_for_status().text
        table = july.split('<section class="panel report-trades"', 1)[1]
        self.assertIn("July 2026 · 7 trades", table)
        self.assertIn('id="report-trades-title">July Trades Report</h2>', table)
        self.assertIn('<h1>Monthly Report</h1>', july)
        self.assertIn('<span>Monthly Report</span>', july)
        self.assertIn('value="2026-07" selected', table)
        self.assertIn("Jul 07, 2026", table)
        self.assertNotIn("Aug 03, 2026", table)
        self.assertEqual(table.count('data-label="Opened"'), 7)
        for removed in ("All-time overview", '<h2>Notes</h2>', 'value="all"', '<section class="stats"'):
            self.assertNotIn(removed, july)
        self.assertGreater(july.index('data-print'), july.index('</table>'))
        current = self.client.get("/report").raise_for_status().text
        legacy = self.client.get("/report?month=all").raise_for_status().text
        self.assertEqual(re.search(r'id="report-trades-title">([^<]+)', current)[1],
                         re.search(r'id="report-trades-title">([^<]+)', legacy)[1])
        self.assertEqual(current.count('data-label="Opened"'), legacy.count('data-label="Opened"'))
        empty = self.client.get("/report?month=2026-01").raise_for_status().text
        self.assertIn("No trades opened in January 2026", empty)
        self.assertEqual(self.client.get("/report?month=2026-13").status_code, 400)
        self.assertEqual(self.client.get("/export/backup").json()["trades"], before)

    def test_monthly_report_includes_every_owned_account_type(self):
        from app import db
        from app.services import report_context
        self.csrf = self.sign_in_as("monthly-accounts@example.com")
        account_ids = []
        with db.session() as conn:
            user = db.user_by_email(conn, "monthly-accounts@example.com")
            for name, kind in [("Report personal", "personal"), ("Combine", "prop"), ("Funded", "prop"), ("Simulated", "sim")]:
                account_ids.append(db.insert_account(conn, user["id"], name, kind, 0, None, None, None))
        for account_id in account_ids:
            self.account = str(account_id)
            self.post_trade(instrument="MES", legs=[
                ("entry", "1", "5800", "2026-10-15T09:35"),
                ("exit", "1", "5810", "2026-10-15T10:00"),
            ])
        self.post_trade(instrument="MNQ", legs=[
            ("entry", "1", "20000", "2026-09-15T09:35"),
            ("exit", "1", "20010", "2026-09-15T10:00"),
        ])
        with db.session() as conn:
            context = report_context(conn, user, "2026-10")
        self.assertEqual({t["account_id"] for t in context["trades"]}, set(account_ids))
        self.assertEqual(len(context["trades"]), 4)
        page = self.client.get("/report?month=2026-10").raise_for_status().text
        self.assertIn("October Trades Report", page)
        self.assertIn("October 2026 · 4 trades · All accounts", page)
        self.assertNotIn('data-label="Opened">Sep', page)

    def test_monthly_views_use_current_journal_timezone_and_private_records(self):
        from app import db
        self.csrf = self.sign_in_as("month-boundary@example.com")
        self.account = account_from(self.client.get("/trades/new").text)
        self.post_trade(instrument="MES", legs=[
            ("entry", "1", "5800", "2026-11-01T00:15"),
            ("exit", "1", "5810", "2026-11-01T00:45"),
        ])
        with db.session() as conn:
            user = db.user_by_email(conn, "month-boundary@example.com")
            db.update_user(conn, user["id"], "America/Los_Angeles", 15)
        october = self.client.get("/reviews?month=2026-10").raise_for_status().text
        self.assertIn('<span>Closed trades</span><strong>1</strong>', october)
        self.assertIn("$50.00", october)
        self.assertIn("No trades closed in this month", self.client.get("/reviews?month=2026-11").text)
        report = self.client.get("/report?month=2026-10").raise_for_status().text
        self.assertEqual(report.count('data-label="Opened"'), 1)
        self.assertIn("Oct 31, 2026 21:15", report)
        self.assertIn("No trades opened in November 2026", self.client.get("/report?month=2026-11").text)

    def test_news_snapshot_corrects_stale_market_date_without_rewriting_stored_news(self):
        from app import db
        from app.services import news_context

        with db.session() as conn:
            # Old installations already have this obsolete row in their seeded snapshot.
            conn.execute(
                """INSERT INTO news_events (title, when_utc, impact, category, actual, forecast, previous, note)
                   VALUES (?, ?, 'low', 'early_close', '', '', '', '')""",
                ("Day before Thanksgiving, early close 1:00 p.m. ET", "2026-11-25T18:00:00Z"),
            )
            user = db.user_by_email(conn, self.email)
            before = db.news_events(conn)
            context = news_context(conn, user)
            self.assertEqual(before, db.news_events(conn))
        self.assertTrue(any(event["ny_date"] == "Fri Nov 27" for event in context["early"]))
        self.assertFalse(any(event["ny_date"] == "Wed Nov 25" for event in context["early"]))
        page = self.client.get("/news").raise_for_status().text
        self.assertIn("Saved snapshot", page)
        self.assertIn("Oct 14, 2026", page)
        self.assertIn("Nov 06, 2026", page)
        self.assertNotIn("GDP and Core PCE have", page)
        self.assertNotIn("Day before Thanksgiving", page)
        for removed in ('<h2>This week</h2>', 'id="news-snapshot"', 'href="#news-snapshot"', 'Watchlist and earnings'):
            self.assertNotIn(removed, page)

    def test_news_calendar_loads_directly_on_its_own_origin(self):
        from html import unescape
        from urllib.parse import urlsplit

        page = self.client.get("/news").raise_for_status().text
        frame = re.search(r'<iframe\b[^>]*title="Tradays economic calendar"[^>]*>', page, re.S)[0]
        source = unescape(re.search(r'src="([^"]+)"', frame)[1])
        self.assertEqual(urlsplit(source).netloc, "www.tradays.com")
        self.assertEqual(urlsplit(source).path, "/en/economic-calendar/widget")
        self.assertIn('loading="eager"', frame)
        self.assertIn("allow-same-origin", frame)
        self.assertIn("allow-scripts", frame)
        self.assertIn("allow-forms", frame)
        # Storage is available only on the provider origin, never in a journal srcdoc.
        self.assertNotIn("srcdoc=", frame)
        self.assertNotIn("<template>", page)
        self.assertNotIn("Show Tradays calendar", page)
        self.assertIn("Calendar unavailable?", page)
        self.assertIn('href="https://www.tradays.com/en"', page)

    def test_privacy_copy_and_active_storage_deletion(self):
        from app import db

        policy = self.client.get("/privacy").raise_for_status().text
        for phrase in ("PostgreSQL", "no-store", "whole-user account deletion", "hosting", "on-page guide"):
            self.assertIn(phrase.lower(), policy.lower())
        page = self.post_trade(
            instrument="ES",
            legs=[("entry", "1", "5800", "2026-10-21T10:00"),
                  ("exit", "1", "5810", "2026-10-21T10:30")],
        )
        self.assertNotIn('class="sample-fill-chart"', page.text)
        trade_id = int(page.url.path.split("/")[-1])
        uploaded = self.client.post(
            f"/trades/{trade_id}/shots", data={"csrf": self.csrf, "slot": "entry"},
            files={"image": ("shot.png", PNG, "image/png")},
        ).raise_for_status()
        shot_id = int(re.search(r"/media/(\d+)", uploaded.text)[1])
        backup = self.client.get("/export/backup").raise_for_status()
        self.assertEqual(backup.headers["Cache-Control"], "private, no-store")
        self.assertTrue(any(t["screenshots"] for t in backup.json()["trades"]))
        with db.session() as conn:
            user_id = db.user_by_email(conn, self.email)["id"]
            filename = db.shots(conn, trade_id)[0]["filename"]
            self.assertEqual(db.media_content(conn, user_id, filename), PNG)
        self.client.post(f"/trades/{trade_id}/delete", data={"csrf": self.csrf}).raise_for_status()
        self.assertEqual(self.client.get(f"/trades/{trade_id}").status_code, 404)
        self.assertEqual(self.client.get(f"/media/{shot_id}").status_code, 404)
        with db.session() as conn:
            self.assertIsNone(db.media_content(conn, user_id, filename))
            self.assertEqual(db.legs(conn, trade_id), [])

    def test_demo_funded_account_has_an_empty_calendar(self):
        from app import db
        from app.sample_data import DEMO_EMAIL, DEMO_FUNDED_NAME

        self.client.get("/demo").raise_for_status()
        with db.session() as conn:
            user_id = db.user_by_email(conn, DEMO_EMAIL)["id"]
            funded = next(row for row in db.accounts(conn, user_id) if row["name"] == DEMO_FUNDED_NAME)
            db.delete_account(conn, user_id, funded["id"])
            trade_ids = {row["id"] for row in db.trades(conn, user_id)}

        # An existing demo session acquires the option without reseeding its fills.
        dashboard = self.client.get("/")
        link = re.search(r'<option value="(\d+)"[^>]*>Topstep Funded</option>', dashboard.text)
        self.assertIsNotNone(link)
        calendar = self.client.get("/", params={"account": link[1], "month": "2026-10", "range": "all"})
        days = re.findall(r'data-date="[^"]+" data-pnl="([^"]+)" data-trades="([^"]+)"', calendar.text)
        self.assertEqual(len(days), 31)
        self.assertTrue(all(float(pnl) == 0 and count == "0" for pnl, count in days))
        self.assertIn("No trades to show", calendar.text)
        self.client.get("/demo").raise_for_status()
        with db.session() as conn:
            funded = [row for row in db.accounts(conn, user_id) if row["name"] == DEMO_FUNDED_NAME]
            self.assertEqual([row["id"] for row in funded], [int(link[1])])
            trades = db.trades(conn, user_id)
            self.assertEqual({row["id"] for row in trades}, trade_ids)
            self.assertTrue(all(row["account_id"] != funded[0]["id"] for row in trades))


    def test_dashboard_account_dropdown_dates_limits_and_all_ranges(self):
        import json
        from zoneinfo import ZoneInfo
        from app import db
        from app.sample_data import DEMO_EMAIL, DEMO_PROP, DEMO_SECOND_COMBINE, DEMO_FUNDED_NAME

        class Today(datetime):
            @classmethod
            def now(cls, tz=None):
                return cls(2026, 11, 14, 12, tzinfo=ZoneInfo("America/New_York")).astimezone(tz)

        with tempfile.TemporaryDirectory() as data, patch.dict(os.environ, {"OMENSITE_DATA": data}), TestClient(app) as demo:
            with patch("app.main.sample_through", return_value=date(2026, 11, 13)), patch("app.services.datetime", Today):
                html = demo.get("/demo").text
                self.assertEqual(html.count('select name="account"'), 1)
                options = re.search(r'<select name="account">(.*?)</select>', html, re.S)[1]
                self.assertEqual(re.findall(r'>([^<>]+)</option>',options),
                                 ["All Accounts",DEMO_PROP["name"],"Topstep Funded",DEMO_SECOND_COMBINE,"Personal","Simulated Trades"])
                masked_numbers = re.findall(r'Account (XXXX\d{3})</p>',html)
                self.assertEqual(len(set(masked_numbers)),2)
                self.assertEqual(masked_numbers,re.findall(r'Account (XXXX\d{3})</p>',demo.get('/').text))
                self.assertNotIn('Simulated Trading Combine',html)
                with db.session() as conn:
                    user_id = db.user_by_email(conn, DEMO_EMAIL)["id"]
                    accounts = {a["name"]:a["id"] for a in db.accounts(conn,user_id)}
                    records = db.trades(conn,user_id)
                original_ids = [t["id"] for t in records]
                for selection in ("", str(accounts[DEMO_PROP["name"]]), str(accounts[DEMO_FUNDED_NAME]),
                                  str(accounts[DEMO_SECOND_COMBINE]), str(accounts["Personal"]), str(accounts["Sim"])):
                    for range_key, cutoff in (("all",None),("7d","2026-11-08"),("30d","2026-10-16"),("mtd","2026-11-01")):
                        with self.subTest(account=selection,range=range_key):
                            can_filter_time = selection in ("", str(accounts["Sim"]))
                            expected = [r for r in records if not selection or r["account_id"] == int(selection)]
                            if cutoff and can_filter_time:
                                expected = [r for r in expected if r["closed_local"][:10] >= cutoff]
                            response = demo.get("/api/dashboard/equity",params={"account":selection,"range":range_key})
                            self.assertEqual(response.status_code,200)
                            self.assertEqual(response.headers["Cache-Control"],"private, no-store")
                            chart = response.json()
                            self.assertEqual({p["id"] for p in chart["points"]},{r["id"] for r in expected})
                            self.assertAlmostEqual(chart["net_pnl"],sum(r["net_pnl"] for r in expected))
                            for point in chart["points"]:
                                record = next(r for r in expected if r["id"] == point["id"])
                                self.assertEqual(point["date"],record["closed_local"][:10])
                                self.assertEqual(point["time"],int(datetime.fromisoformat(record["closed_at"].replace("Z","+00:00")).timestamp()*1000))
                            page = demo.get("/",params={"account":selection,"range":range_key}).text
                            embedded = json.loads(re.search(r'data-equity-data>(.*?)</script>',page,re.S)[1]) if expected else None
                            if embedded:
                                self.assertEqual(embedded["points"],chart["points"])
                            controls = re.search(r'data-account-filter>(.*?)</form>',page,re.S)[1]
                            if can_filter_time:
                                for key,label in (("7d","7D"),("30d","30D"),("mtd","MTD"),("all","All")):
                                    suffix = "&account=" + selection if selection else ""
                                    self.assertIn(f'href="/?range={key}{suffix}">{label}</a>', controls)
                            else:
                                self.assertNotIn('class="pill-toggle',controls)
                                self.assertIn('name="range" value="all"',controls)
                                self.assertIsNone(chart["since"])
                            if selection in ("",str(accounts["Sim"]),str(accounts["Personal"])):
                                self.assertIsNone(chart["rules"])
                                self.assertEqual(chart["limits"],[])
                for name, net, adjusted, start, end in (
                    (DEMO_PROP["name"],3135,3000,"2026-10-01","2026-10-13"),
                    (DEMO_SECOND_COMBINE,2426.5,3399.10,"2026-11-09","2026-11-13"),
                ):
                    chart = demo.get("/api/dashboard/equity",params={"account":accounts[name]}).json()
                    self.assertEqual(chart["net_pnl"],net)
                    self.assertEqual(chart["rules"]["base_target"],3000)
                    self.assertEqual(chart["rules"]["current_target"],adjusted)
                    self.assertEqual(chart["rules"]["current_balance_floor"],50000)
                    self.assertEqual(chart["points"][0]["date"],start)
                    self.assertEqual(chart["points"][-1]["date"],end)
                    self.assertEqual({p["account_id"] for p in chart["points"]},{accounts[name]})
                with db.session() as conn:
                    from app.services import dashboard_context
                    context = dashboard_context(conn, db.user_by_id(conn,user_id))
                    second = next(p for p in context["props"] if p["account"]["id"] == accounts[DEMO_SECOND_COMBINE])
                    self.assertEqual(second["combine_room"],2426.5)
                    self.assertEqual(second["combine_drawdown"],192)
                with db.session() as conn:
                    self.assertEqual(original_ids,[t["id"] for t in db.trades(conn,user_id)])
                demo.cookies.clear()
                self.assertEqual(demo.get("/api/dashboard/equity",follow_redirects=False).status_code,303)

    def test_account_rules_are_explicit_scoped_and_survive_backup(self):
        from app import db
        from app.equity import TOPSTEP_EOD
        from app.services import restore_backup, export_backup
        token = self.sign_in_as("equity-owner@example.com")
        created = self.client.post("/settings/accounts",data={
            "csrf":token,"name":"Topstep Combine test","kind":"prop","starting_balance":"50000",
            "profit_target":"3000","trailing_drawdown":"2000","daily_loss_limit":""
        })
        self.assertEqual(created.status_code,200)
        with db.session() as conn:
            owner = db.user_by_email(conn,"equity-owner@example.com")
            account = next(a for a in db.accounts(conn,owner["id"]) if a["name"] == "Topstep Combine test")
        missing = self.client.get("/api/dashboard/equity",params={"account":account["id"]}).json()
        self.assertIsNone(missing["rules"])
        self.assertTrue(missing["warning"])
        config = {"csrf":token,"rule_profile":TOPSTEP_EOD,"starting_balance":"50000",
                  "profit_target":"3000","trailing_drawdown":"2000","consistency_pct":"55","daily_loss_limit":""}
        good = self.client.post(f'/settings/accounts/{account["id"]}/rules',data=config)
        self.assertEqual(good.status_code,200)
        self.assertIsNotNone(self.client.get("/api/dashboard/equity",params={"account":account["id"]}).json()["rules"])
        invalid = self.client.post(f'/settings/accounts/{account["id"]}/rules',data={**config,"profit_target":"5000"})
        self.assertEqual(invalid.status_code,400)
        with db.session() as conn:
            self.assertEqual(db.account(conn,owner["id"],account["id"])["profit_target"],3000)
            backup = export_backup(conn,owner)
        other_token = self.sign_in_as("equity-other@example.com")
        denied = self.client.post(f'/settings/accounts/{account["id"]}/rules',data={**config,"csrf":other_token})
        self.assertEqual(denied.status_code,400)
        with db.session() as conn:
            other = db.user_by_email(conn,"equity-other@example.com")
            restore_backup(conn,other,backup)
            restored = next(a for a in db.accounts(conn,other["id"]) if a["name"] == account["name"])
            self.assertEqual(restored["rule_profile"],TOPSTEP_EOD)
            self.assertEqual(restored["consistency_pct"],55)

    def test_downloads_disable_shared_caching(self):
        for path in ("/export/trades", "/export/backup", "/export.csv", "/export.json"):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.headers["Cache-Control"], "private, no-store")
        self.client.cookies.clear()
        self.assertEqual(self.client.get("/export/trades", follow_redirects=False).status_code, 303)

    def test_discord_sign_in_paths(self):
        from app import db
        from app.services import login_discord, start_session

        self.client.cookies.clear()
        blocked = self.client.get("/auth/discord", follow_redirects=False)
        self.assertIn(blocked.status_code, (303, 503))
        if blocked.status_code == 503:
            self.assertIn("Discord sign-in is not available yet.", blocked.text)
        else:
            self.assertIn("discord.com", blocked.headers["location"])
        stale = self.client.get("/auth/discord/callback?code=abc&state=not-the-cookie")
        self.assertEqual(stale.status_code, 400)
        self.assertNotIn("Sign out", stale.text)
        with db.session() as conn:
            user_id = login_discord(
                conn,
                {
                    "id": "123456789012345678",
                    "username": "ada",
                    "global_name": "Ada Lane",
                    "email": "ada@example.com",
                    "verified": True,
                },
            )
            token = start_session(conn, user_id)
            again = login_discord(
                conn,
                {"id": "123456789012345678", "username": "ada", "global_name": "Ada Lane", "verified": True},
            )
        self.assertEqual(again, user_id)
        self.client.cookies.set("omensite_session", token)
        page = self.client.get("/")
        self.assertIn("Ada Lane", page.text)
        self.assertIn("<h1>Dashboard</h1>", page.text)
        self.assertIn("Equity", page.text)

    def test_es_winner_is_495_50(self):
        page = self.post_trade(
            fees="4.50",
            stop="4990",
            target="5020",
            legs=[
                ("entry", "1", "5000", "2026-10-21T10:00"),
                ("exit", "1", "5010", "2026-10-21T10:30"),
            ],
        )
        self.assertIn("$495.50", page.text)
        self.assertIn("NY AM Silver Bullet", page.text)
        dash = self.client.get("/")
        self.assertIn("$495.50", dash.text)

    def test_partial_mes_stays_open(self):
        page = self.post_trade(
            instrument="MES",
            legs=[
                ("entry", "2", "5800", "2026-10-21T11:00"),
                ("exit", "1", "5810", "2026-10-21T11:20"),
            ],
        )
        self.assertIn("<dt>Exit time</dt><dd>Still open</dd>", page.text)
        self.assertIn("$50.00", page.text)

    def test_news_flags_housing_and_permits(self):
        page = self.post_trade(
            instrument="NQ",
            direction="short",
            stop="20010",
            legs=[
                ("entry", "1", "20000", "2026-10-20T08:20"),
                ("exit", "1", "20002", "2026-10-20T08:40"),
            ],
        )
        self.assertIn("Housing Starts", page.text)
        self.assertIn("Building Permits", page.text)
        self.assertIn("10 minutes", page.text)

    def test_csv_short_previews_and_confirms(self):
        from app import db
        with db.session() as conn:
            user = db.user_by_email(conn, self.email)
            import_account = str(db.insert_account(conn, user["id"], "Import destination", "personal", 0, None, None, None))
        text = (
            "symbol,side,qty,price,time\n"
            "NQ,sell,1,20000,2026-10-01 03:20:00\n"
            "NQ,buy,1,20002,2026-10-01 04:00:00\n"
        )
        preview = self.client.post(
            "/import/preview",
            data={"csrf": self.csrf, "account_id": import_account},
            files={"file": ("fills.csv", text.encode("utf-8"), "text/csv")},
        )
        self.assertEqual(preview.status_code, 200, preview.text[:800])
        self.assertIn(">short<", preview.text)
        self.assertEqual(preview.text.count(f'<option value="{import_account}" selected>'), 2)
        token = re.search(r'name="token" value="([^"]+)"', preview.text)
        self.assertIsNotNone(token)
        done = self.client.post(
            "/import/confirm",
            data={"csrf": self.csrf, "token": token.group(1), "account_id": import_account},
        )
        self.assertIn("Imported 1", done.text)
        with db.session() as conn:
            saved = [t for t in db.trades(conn, user["id"]) if str(t["account_id"]) == import_account]
            self.assertEqual(len(saved), 1)
            self.assertEqual(saved[0]["net_pnl"], -40)

    def test_import_preview_validates_account_and_keeps_selection_on_bad_csv(self):
        from app import db
        self.fixture_session("other-import@example.com")
        with db.session() as conn:
            other = db.user_by_email(conn, "other-import@example.com")
            other_account = str(db.accounts(conn, other["id"])[0]["id"])
        for account in ("", other_account, "invalid"):
            response = self.client.post("/import/preview", data={"csrf": self.csrf, "account_id": account},
                                        files={"file": ("bad.csv", b"wrong,columns\n1,2\n", "text/csv")})
            self.assertEqual(response.status_code, 400)
            self.assertIn("Choose an account.", response.text)
            self.assertNotIn('name="token"', response.text)
        invalid = self.client.post("/import/preview", data={"csrf": self.csrf, "account_id": self.account},
                                   files={"file": ("bad.csv", b"wrong,columns\n1,2\n", "text/csv")})
        self.assertEqual(invalid.status_code, 400)
        self.assertIn("Unrecognized columns", invalid.text)
        self.assertIn(f'<option value="{self.account}" selected>', invalid.text)
        self.assertNotIn('action="/import/confirm"', invalid.text)

    def test_screenshot_markup_and_privacy(self):
        page = self.post_trade(
            instrument="RTY",
            stop="2100",
            legs=[
                ("entry", "1", "2000", "2026-10-16T10:00"),
                ("exit", "1", "2010", "2026-10-16T10:20"),
            ],
        )
        trade_id = page.url.path.rstrip("/").split("/")[-1]
        uploaded = self.client.post(
            f"/trades/{trade_id}/shots",
            data={"csrf": self.csrf, "slot": "entry"},
            files={"image": ("shot.png", PNG, "image/png")},
        )
        self.assertEqual(uploaded.status_code, 200, uploaded.text[:500])
        shot = re.search(r"/media/(\d+)", uploaded.text)
        self.assertIsNotNone(shot)
        shot_id = shot.group(1)
        media = self.client.get(f"/media/{shot_id}")
        self.assertEqual(media.status_code, 200)
        self.assertEqual(media.content, PNG)
        saved = self.client.post(
            f"/trades/{trade_id}/shots/{shot_id}/markup",
            json={
                "shapes": [
                    {
                        "type": "arrow",
                        "color": "#d7b56d",
                        "x1": 0.1,
                        "y1": 0.2,
                        "x2": 0.4,
                        "y2": 0.5,
                        "text": "FVG",
                    }
                ]
            },
            headers={"X-CSRF": self.csrf},
        )
        self.assertEqual(saved.status_code, 200)
        self.assertEqual(saved.json()["ok"], True)
        again = self.client.get(f"/trades/{trade_id}")
        self.assertIn("arrow", again.text)
        self.assertIn("FVG", again.text)
        from app.catalog import MARKUP_COLORS
        for color in MARKUP_COLORS:
            with self.subTest(markup_color=color):
                saved = self.client.post(
                    f"/trades/{trade_id}/shots/{shot_id}/markup",
                    json={"shapes": [{"type": "line", "color": color,
                                      "x1": 0.1, "y1": 0.2, "x2": 0.4, "y2": 0.5}]},
                    headers={"X-CSRF": self.csrf},
                )
                self.assertEqual(saved.status_code, 200)
                self.assertTrue(saved.json()["ok"])
        backup = self.client.get("/export.json")
        self.assertEqual(backup.status_code, 200)
        self.sign_in_as("private@example.com")
        self.assertEqual(self.client.get(f"/trades/{trade_id}").status_code, 404)
        self.assertEqual(self.client.get(f"/media/{shot_id}").status_code, 404)
        csrf = csrf_from(self.client.get("/settings").text)
        restored = self.client.post(
            "/settings/restore",
            data={"csrf": csrf},
            files={"backup": ("backup.json", backup.content, "application/json")},
        )
        self.assertIn("Backup added", restored.text)
        trades = self.client.get("/trades")
        self.assertIn("RTY", trades.text)
        self.assertEqual(self.client.get(f"/trades/{trade_id}").status_code, 404)

    def test_plan_save_copy_source_and_legacy_review_survive(self):
        from app import db
        csrf = self.sign_in_as("plan-copy@example.com")
        headers = {"Accept": "application/json"}
        prep = {"csrf": csrf, "day": "2026-11-13", "bias": "Bullish", "draw": "BSL",
                "key_levels": "Prior high", "news_to_watch": "CPI", "eod_review": "Legacy notes",
                "plan_followed": "Waited for displacement", "tomorrow_change": "Be patient"}
        result = self.client.post("/plan", data=prep, headers=headers)
        self.assertEqual(result.json(), {"saved": True, "day": "2026-11-13"})
        current = dict(prep, day="2026-11-17", eod_review="Keep today’s notes", plan_followed="Today’s review")
        self.client.post("/plan", data=current, headers=headers).raise_for_status()
        self.client.post("/plan", data={"csrf": csrf, "day": "2026-11-16", "eod_review": "Review only"}, headers=headers).raise_for_status()
        ctx = self.client.get("/plan?day=2026-11-17", headers=headers).json()
        self.assertEqual(ctx["previous_plan"]["day"], "2026-11-13")
        self.assertEqual(set(ctx["previous_plan"]), {"day", "bias", "draw", "key_levels", "news_to_watch"})
        self.assertEqual(ctx["plan"]["eod_review"], "Keep today’s notes")
        self.assertEqual(ctx["plan"]["plan_followed"], "Today’s review")
        # Older clients must not clear the new review prompts they don't send.
        legacy = {k:v for k,v in current.items() if k not in {"plan_followed", "tomorrow_change"}}
        self.client.post("/plan", data=legacy).raise_for_status()
        self.assertEqual(self.client.get("/plan?day=2026-11-17", headers=headers).json()["plan"]["plan_followed"], "Today’s review")
        backup = self.client.get("/export/backup").json()
        self.sign_in_as("plan-restore@example.com")
        with db.session() as conn:
            from app.services import restore_backup
            restore_backup(conn, db.user_by_email(conn, "plan-restore@example.com"), backup)
        restored = self.client.get("/plan?day=2026-11-17", headers=headers).json()
        self.assertEqual(restored["plan"], ctx["plan"])

    def test_plan_validation_and_storage_failure_preserve_saved_data(self):
        from app import db
        csrf = self.sign_in_as("plan-errors@example.com")
        data = {"csrf": csrf, "day": "2026-11-17", "key_levels": "Original", "eod_review": "Existing review"}
        headers = {"Accept": "application/json"}
        self.client.post("/plan", data=data, headers=headers).raise_for_status()
        changed = dict(data, key_levels="Unsaved level", eod_review="Draft review", plan_followed="Draft answer", bias="invalid")
        failed = self.client.post("/plan", data=changed, headers=headers)
        self.assertEqual(failed.status_code, 400)
        self.assertFalse(failed.json()["saved"])
        html = self.client.post("/plan", data=changed)
        self.assertEqual(html.status_code, 400)
        self.assertIn("Unsaved level</textarea>", html.text)
        self.assertIn("Draft review</textarea>", html.text)
        self.assertIn('data-save-error="true"', html.text)
        changed["bias"] = "Bullish"
        real_save = db.save_day
        def broken_save(*args, **kwargs):
            real_save(*args, **kwargs)
            raise RuntimeError("injected transaction failure")
        with patch("app.db.save_day", side_effect=broken_save), self.assertLogs("app.main", level="ERROR"):
            failed = self.client.post("/plan", data=changed, headers=headers)
        self.assertEqual(failed.status_code, 503)
        self.assertFalse(failed.json()["saved"])
        ctx = self.client.get("/plan?day=2026-11-17", headers=headers).json()
        self.assertEqual(ctx["plan"]["key_levels"], "Original")
        self.assertEqual(ctx["plan"]["eod_review"], "Existing review")
        changed["csrf"] = "invalid"
        self.assertEqual(self.client.post("/plan", data=changed, headers=headers).status_code, 403)

    def test_plan_dates_use_current_zone_and_isolate_users(self):
        from app import db
        from zoneinfo import ZoneInfo
        csrf = self.sign_in_as("plan-zone@example.com")
        class FixedNow(datetime):
            @classmethod
            def now(cls, tz=None):
                return datetime(2026, 11, 18, 2, tzinfo=ZoneInfo("UTC")).astimezone(tz)
        headers = {"Accept": "application/json"}
        self.client.post("/plan", data={"csrf": csrf, "day": "2026-11-16", "key_levels": "Private level"}).raise_for_status()
        with patch("app.services.datetime", FixedNow):
            ctx = self.client.get("/plan", headers=headers).json()
        self.assertEqual(ctx["day"], "2026-11-17")
        self.assertEqual(ctx["previous_day"], "2026-11-16")
        self.assertEqual(ctx["next_day"], "2026-11-18")
        # Demo trades use saved UTC fills, even after the journal zone changes.
        self.client.get("/demo")
        ny = self.client.get("/plan?day=2026-11-16", headers=headers).json()
        self.assertEqual(len(ny["opened"]), 4)
        with db.session() as conn:
            demo_id = db.user_by_email(conn, "demo@omensite.journal")["id"]
            conn.execute("UPDATE users SET timezone = ? WHERE id = ?", ("Asia/Tokyo", demo_id))
        try:
            tokyo = self.client.get("/plan?day=2026-11-17", headers=headers).json()
            crossing = {t["id"] for t in ny["opened"] if datetime.fromisoformat(t["opened_at"].replace("Z", "+00:00")).astimezone(ZoneInfo("Asia/Tokyo")).date() == date(2026, 11, 17)}
            self.assertEqual(len(crossing), 2)
            self.assertEqual(crossing, {t["id"] for t in tokyo["opened"] if t["opened_at"].startswith("2026-11-16")})
        finally:
            with db.session() as conn:
                conn.execute("UPDATE users SET timezone = ? WHERE id = ?", ("America/New_York", demo_id))
        self.sign_in_as("plan-other@example.com")
        ctx = self.client.get("/plan?day=2026-11-17", headers=headers).json()
        self.assertIsNone(ctx["previous_plan"])
        self.assertFalse(ctx["plan_saved"])
        page = self.client.get("/plan?day=2026-11-17&notice=plan")
        self.assertNotIn("The day's plan is saved", page.text)
        self.assertEqual(self.client.get("/plan?day=invalid").status_code, 400)
        self.assertEqual(self.client.get("/plan?day=0001-01-01").status_code, 200)
        self.assertEqual(self.client.get("/plan?day=9999-12-31").status_code, 200)
        self.client.cookies.clear()
        self.assertEqual(self.client.get("/plan", follow_redirects=False).status_code, 303)

    def test_playbook_duplicate_is_a_draft_and_preserves_trade_text_and_charts(self):
        from app import db
        self.csrf = self.sign_in_as("playbook-duplicate@example.com")
        self.account = account_from(self.client.get("/trades/new").text)
        self.post_trade(legs=[("entry", "1", "5820", "2026-11-17T09:35"), ("exit", "1", "5830", "2026-11-17T10:05")])
        with db.session() as conn:
            uid = db.user_by_email(conn, "playbook-duplicate@example.com")["id"]
            trade = db.trades(conn, uid)[0]
            conn.execute("UPDATE trades SET setup = ? WHERE id = ? AND user_id = ?", ("Opening sweep", trade["id"], uid))
        setup = dict(csrf=self.csrf, name="Opening sweep", setup="Wait for displacement.", rules="Retest only.", example_notes="Review the open.")
        headers = {"Accept": "application/json"}
        source = self.client.post("/playbook", data=setup, headers=headers).raise_for_status().json()
        self.assertTrue(source["saved"])
        chart = self.client.post(f'/playbook/{source["id"]}/images', data={"csrf": self.csrf}, files={"image": ("es.png", PNG, "image/png")})
        self.assertEqual(chart.status_code, 200)
        original = self.client.get(source["url"], headers=headers).json()
        self.assertEqual(len(original["charts"]), 1)
        self.assertEqual(self.client.get(original["charts"][0]["url"]).content, PNG)
        index = self.client.get("/playbook?q=SWEEP", headers=headers).json()
        self.assertEqual(index["setups"], [dict(id=source["id"], name="Opening sweep", summary="Wait for displacement.", chart_count=1)])
        self.assertIn("No matching setups", self.client.get("/playbook?q=other").text)
        draft = self.client.get(f'/playbook/new?copy={source["id"]}')
        self.assertIn('value="Opening sweep (copy)"', draft.text)
        self.assertIn("Retest only.</textarea>", draft.text)
        self.assertNotIn(original["charts"][0]["url"], draft.text)
        self.assertEqual(self.client.get("/playbook", headers=headers).json()["total"], 1)
        copied = self.client.post("/playbook", data=dict(setup, name="Opening sweep (copy)"), headers=headers).json()
        self.assertNotEqual(copied["id"], source["id"])
        self.assertEqual(self.client.get(copied["url"], headers=headers).json()["charts"], [])
        changed = self.client.post(f'/playbook/{copied["id"]}', data=dict(setup, name="Retest variant"))
        self.assertIn('role="status">Saved</p>', changed.text)
        self.assertEqual(self.client.get(source["url"], headers=headers).json(), original)
        self.assertEqual(self.client.get("/export/backup").json()["trades"][0]["setup"], "Opening sweep")
        self.sign_in_as("another-playbook@example.com")
        self.assertEqual(self.client.get(f'/playbook/new?copy={source["id"]}').status_code, 404)
        self.assertEqual(self.client.get(source["url"]).status_code, 404)

    def test_playbook_failed_save_keeps_draft_and_rolls_back(self):
        from app import db
        csrf = self.sign_in_as("playbook-failure@example.com")
        headers = {"Accept": "application/json"}
        fields = dict(csrf=csrf, name="Original", setup="Original criteria", rules="", example_notes="Existing notes")
        item = self.client.post("/playbook", data=fields, headers=headers).json()
        path = f'/playbook/{item["id"]}'
        validation = self.client.post(path, data=dict(fields, name="  ", example_notes="Draft notes"))
        self.assertEqual(validation.status_code, 400)
        self.assertIn('aria-invalid="true"', validation.text)
        self.assertIn("Enter a setup name.", validation.text)
        self.assertIn("Draft notes</textarea>", validation.text)
        invalid = self.client.post("/playbook", data=dict(fields, rules="x"*8001), headers=headers)
        self.assertEqual(invalid.status_code, 400)
        self.assertIn("rules", invalid.json()["fields"])
        real_update = db.update_playbook

        def broken_save(*args, **kwargs):
            real_update(*args, **kwargs)
            raise RuntimeError("injected storage failure")

        with patch("app.db.update_playbook", side_effect=broken_save), self.assertLogs("app.main", level="ERROR"):
            failure = self.client.post(path, data=dict(fields, example_notes="Draft notes"), headers=headers)
        self.assertEqual(failure.status_code, 503)
        self.assertFalse(failure.json()["saved"])
        self.assertEqual(self.client.get(path, headers=headers).json()["example_notes"], "Existing notes")
        self.assertEqual(self.client.post(path, data=dict(fields, csrf="bad"), headers=headers).status_code, 403)

    def test_sample_journal_insights(self):
        self.sign_in_as("sample@example.com")
        csrf = csrf_from(self.client.get("/settings").text)
        loaded = self.client.post("/settings/sample", data={"csrf": csrf})
        self.assertIn("Sample trades are in the journal.", loaded.text)
        self.assertIn("NY AM FVG trades average", loaded.text)
        self.assertIn("London trades are down", loaded.text)
        self.assertIn("Sample Prop", loaded.text)
        again = self.client.post("/settings/sample", data={"csrf": csrf})
        self.assertIn("The sample journal is already loaded.", again.text)


if __name__ == "__main__":
    unittest.main()
