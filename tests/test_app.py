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
        self.assertIn('id="hero-title"', home.text)
        self.assertIn("Your edge.", home.text)
        self.assertIn("Your trades. Your patterns. Your edge.", home.text)
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
        self.assertIn("Initial Jobless Claims", news.text)
        self.assertIn("Marked high in this journal", news.text)
        self.assertIn("noindex", news.text)

    def test_intro_and_dashboard_shell(self):
        self.client.cookies.clear()
        intro = self.client.get("/")
        self.assertIn('href="/signup"', intro.text)
        self.assertIn('href="/demo"', intro.text)
        self.assertIn('role="tablist"', intro.text)
        self.assertIn("/static/js/landing.js", intro.text)
        self.assertIn("Learn from Omen. Make better trades.", intro.text)
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
        self.assertIn("Topstep 50k Combine", demo.text)
        self.assertEqual(self.client.cookies.get("omensite_session"), self.session)
        self.assertTrue(self.client.cookies.get("omensite_demo"))
        token = csrf_from(demo.text)
        demo_session = self.client.cookies.get("omensite_demo")
        for path in ("/trades", "/settings/profile", "/settings/sample", "/import/confirm"):
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

        # The completed account stays visible even with a range that excludes its fills.
        demo = self.client.get("/", params={"range": "mtd", "account": account_id})
        self.assertEqual(demo.status_code, 200)
        self.assertIn("Topstep 50k Combine", demo.text)
        self.assertRegex(demo.text, r"Simulated Trading Combine · Account \d+XXXX · Passed Oct 13, 2026")
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
        self.assertIn("Topstep 50k Combine", renamed.text)
        self.assertNotIn(previous_name, renamed.text)
        with db.session() as conn:
            self.assertEqual(db.account(conn, user_id, account_id)["name"], "Topstep 50k Combine")
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
        link = re.search(r'href="(/\?account=(\d+)&range=all)">Topstep 50k Funded</a>', dashboard.text)
        self.assertIsNotNone(link)
        calendar = self.client.get(link[1] + "&month=2026-10")
        days = re.findall(r'data-date="[^"]+" data-pnl="([^"]+)" data-trades="([^"]+)"', calendar.text)
        self.assertEqual(len(days), 31)
        self.assertTrue(all(float(pnl) == 0 and count == "0" for pnl, count in days))
        self.assertIn("No trades to show", calendar.text)
        self.client.get("/demo").raise_for_status()
        with db.session() as conn:
            funded = [row for row in db.accounts(conn, user_id) if row["name"] == DEMO_FUNDED_NAME]
            self.assertEqual([row["id"] for row in funded], [int(link[2])])
            trades = db.trades(conn, user_id)
            self.assertEqual({row["id"] for row in trades}, trade_ids)
            self.assertTrue(all(row["account_id"] != funded[0]["id"] for row in trades))

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
        self.assertIn("Still open", page.text)
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
        text = (
            "symbol,side,qty,price,time\n"
            "NQ,sell,1,20000,2026-10-01 03:20:00\n"
            "NQ,buy,1,20002,2026-10-01 04:00:00\n"
        )
        preview = self.client.post(
            "/import/preview",
            data={"csrf": self.csrf},
            files={"file": ("fills.csv", text.encode("utf-8"), "text/csv")},
        )
        self.assertEqual(preview.status_code, 200, preview.text[:800])
        self.assertIn(">short<", preview.text)
        token = re.search(r'name="token" value="([^"]+)"', preview.text)
        self.assertIsNotNone(token)
        done = self.client.post(
            "/import/confirm",
            data={"csrf": self.csrf, "token": token.group(1), "account_id": self.account},
        )
        self.assertIn("Imported 1", done.text)

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
