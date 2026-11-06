"""Shared trade history for the public preview and read-only demo."""

from datetime import date, datetime, timedelta
from functools import lru_cache
from random import Random

from app.analytics import dashboard, month_calendar, prop_rows
from app.instruments import FUTURES
from app.news_data import NY, build_events
from app.present import equity_svg


DEMO_EMAIL = "demo@omensite.journal"
DEMO_NOTE = "Omensite demo v4"
DEMO_FUNDED_NAME = "Topstep 50k Funded"
LEGACY_DEMO_PROP = "Sample Prop"
FORMER_DEMO_PROP_NAMES = (LEGACY_DEMO_PROP, "TopstepX 50K account")
CHALLENGE_START = date(2026, 10, 1)
CHALLENGE_END = date(2026, 10, 13)
DEMO_PROP = {
    "name": "Topstep 50k Combine",
    "kind": "prop",
    "starting_balance": 50000,
    "daily_loss_limit": 1000,
    "trailing_drawdown": 2000,
    "profit_target": 3000,
    "consistency_pct": 55,
}
START = date(2026, 7, 1)
ROLLING_START = date(2026, 11, 1)

# Gross results in dollars, before the same $4.50 fee charged to each trade.
# Each row is one session; mixed outcomes give realistic daily win rates.
HISTORY = {
    7: {
        7: (425,), 10: (-175,), 16: (600, 287.5), 21: (-237.5,),
        27: (725,), 30: (400,),
    },
    8: {
        3: (-225, 175), 4: (-425, -250, 187.5), 6: (400, -275), 7: (-450,),
        10: (-175, 325, -400), 12: (137.5, -200), 13: (-325, -325, -137.5),
        14: (575, 100), 17: (-275, -300, 200), 19: (-350,), 20: (325, -187.5, 187.5),
        21: (-375, -125), 24: (-525, 250, -250), 26: (312.5, -137.5),
        28: (-425, 275), 31: (-150,),
    },
    9: {
        1: (250, -175), 3: (-250,), 8: (375, -225), 10: (-287.5,),
        14: (-150, 287.5), 17: (237.5,), 22: (-337.5,), 24: (325,), 29: (87.5,),
    },
}
OCTOBER_SESSIONS = (
    (-175, 112.5), (450,), (325, -125, 562.5), (875, -200),
    (-250, 137.5, -212.5), (325, 225), (162.5, -87.5, 287.5, 100),
    (525, -162.5, 350), (-225,), (700, -175, 437.5),
    (212.5, -112.5), (375,), (225, 187.5, -150, -100, 312.5),
    (537.5, -187.5, 262.5), (-287.5, 100), (650, 175),
    (262.5, -125, 150, 325), (-312.5, -137.5, 200),
    (487.5, 362.5), (550, -175, 237.5),
)
HISTORY[10] = dict(zip(
    (1, 2, 5, 6, 7, 9, 12, 13, 14, 15, 16, 19, 20, 22, 23, 26, 27, 28, 29, 30),
    OCTOBER_SESSIONS,
    strict=True,
))
HOLIDAYS = frozenset(date.fromisoformat(row["when_utc"][:10])
                     for row in build_events() if row["category"] == "holiday")


def sample_through(now: datetime | None = None) -> date:
    """Publish the day's sample after the simulated New York morning closes."""
    now = now.astimezone(NY) if now is not None else datetime.now(NY)
    return now.date() - timedelta(days=now.hour < 13)


def _session(day: date) -> tuple[float, ...]:
    if day < ROLLING_START:
        return HISTORY[day.month].get(day.day, ())
    if day.weekday() >= 5 or day in HOLIDAYS:
        return ()
    rng = Random(day.toordinal())
    if rng.random() >= .65:
        return ()
    return tuple(
        rng.randint(7, 54) * 12.5 if rng.random() < .55 else -rng.randint(6, 36) * 12.5
        for _ in range(rng.randint(1, 4))
    )


def sample_trades(through: date | None = None) -> tuple[dict, ...]:
    """Return the same closed trades for the same date, in entry order."""
    return _sample_trades(through or sample_through())


def demo_trade_plan(instrument: str, direction: str, entry: float, qty: float,
                    opened: datetime, net_pnl: float) -> dict[str, float]:
    """Build a 2:1 plan from the entry without changing the simulated fills."""
    spec = FUTURES[instrument]
    dollars_per_point = qty * spec.point_value
    if instrument in {"MES", "MNQ"}:
        # The two requested ranges overlap at 20–30 stop points for an exact 2:1 plan.
        minute = opened.hour * 60 + opened.minute
        stop_points = 20 + (opened.toordinal() + minute) % 11
    else:
        stop_ticks = max(1, round(250 / (dollars_per_point * spec.tick)))
        stop_points = stop_ticks * spec.tick
    sign = 1 if direction == "long" else -1
    risk = stop_points * dollars_per_point
    return {
        "stop": entry - sign * stop_points,
        "target": entry + sign * 2 * stop_points,
        "risk_dollars": round(risk, 2),
        "planned_r": 2.0,
        "r_multiple": round(net_pnl / risk, 4),
    }


def demo_ict_context(setup: str, direction: str, stop: float, target: float) -> tuple[dict, list[str]]:
    """Describe the simulated setup that accompanies the recorded trade plan."""
    long = direction == "long"
    sweep = "Sell-side liquidity sweep" if long else "Buy-side liquidity sweep"
    edge = "low" if long else "high"
    liquidity = "buy-side" if long else "sell-side"
    tags, scenario = {
        "Opening range": (
            [sweep, "MSS"],
            f"Price swept the {edge} of the opening range, then displaced through the last opposing swing. "
            "The entry was on a retest of the broken swing.",
        ),
        "Liquidity sweep": (
            [sweep, "MSS", "FVG"],
            f"Price swept a prior swing {edge}. Displacement shifted market structure and left a fair value gap. "
            "The entry was on a retracement into that gap.",
        ),
        "Fair value gap": (
            ["BOS", "FVG"],
            "Displacement broke a swing in the direction of the higher-timeframe bias. "
            "The entry was on a retracement into the fair value gap left by the move.",
        ),
        "Break & retest": (
            ["BOS", "Order Block"],
            "Displacement broke a swing in the direction of the higher-timeframe bias. "
            "The entry was on a retest of the last opposing candle before the break.",
        ),
    }[setup]
    return {
        "htf_bias": "Bullish" if long else "Bearish",
        "draw": "BSL" if long else "SSL",
        "premium": "Discount" if long else "Premium",
        "range_low": min(stop, target),
        "range_high": max(stop, target),
        "lesson": f"Simulated setup. {scenario} The plan targeted {liquidity} liquidity at {target:g}, "
                  f"with invalidation at {stop:g}.",
    }, tags


@lru_cache(maxsize=2)
def _sample_trades(through: date) -> tuple[dict, ...]:
    records = []
    for offset in range((through - START).days + 1):
        day = START + timedelta(days=offset)
        for slot, gross in enumerate(_session(day)):
            index = len(records)
            instrument, qty, entry = (
                ("MES", 2, 5800), ("NQ", 1, 20125),
                ("ES", 1, 5800), ("MNQ", 5, 20125),
            )[index % 4]
            if instrument == "NQ" and gross % FUTURES["NQ"].tick_value:
                instrument, qty = "MNQ", 5
            multiplier = FUTURES[instrument].point_value
            direction = "short" if index % 3 == 1 else "long"
            exit_price = entry + gross / (qty * multiplier) * (-1 if direction == "short" else 1)
            stamp = f"{day.isoformat()}T{9 + slot // 2:02d}:{35 + (slot % 2) * 20:02d}:00"
            opened = datetime.fromisoformat(stamp)
            net = gross - 4.5
            setup = ("Opening range", "Liquidity sweep", "Fair value gap", "Break & retest")[index % 4]
            plan = demo_trade_plan(instrument, direction, entry, qty, opened, net)
            ict, tags = demo_ict_context(setup, direction, plan["stop"], plan["target"])
            records.append({
                "id": index + 1, "instrument": instrument, "qty": qty,
                "is_prop": CHALLENGE_START <= day <= CHALLENGE_END,
                "direction": direction, "entry": entry, "exit": exit_price,
                "fees": 4.5, "is_closed": 1, "net_pnl": net,
                "opened_at": stamp, "closed_at": (opened + timedelta(minutes=18 + index % 29)).isoformat(),
                **plan,
                "followed_plan": int(net > 0 or index % 4 != 0),
                "left_on_table": 0, "session": "NY AM", "kill_zone": "NY AM",
                "grade": "A+" if net > 0 else "B", "emotion_before": "Calm" if net > 0 else "Anxious",
                "setup": setup, "ict": ict, "tags": tags,
            })
    return tuple(records)


def demo_challenge(row: dict) -> dict:
    """Label the fixed, completed sample challenge in both demo views."""
    passed = (row["total_pnl"] >= DEMO_PROP["profit_target"]
              and row["best_share"] is not None
              and row["best_share"] <= DEMO_PROP["consistency_pct"] / 100)
    return {"account_number": "892849XXXX", "passed_on": CHALLENGE_END if passed else None}


def sample_overview(through: date | None = None) -> dict:
    through = through or sample_through()
    trades = sample_trades(through)
    board = dashboard(trades, {trade["id"]: trade["tags"] for trade in trades})
    month = date.fromisoformat(trades[-1]["closed_at"][:10]) if trades else through
    recent = list(reversed(trades))
    review = next((trade for trade in recent if trade["setup"] == "Liquidity sweep"
                   and trade["direction"] == "long" and trade["net_pnl"] > 0), None)
    prop = prop_rows([dict(DEMO_PROP, id=1)], [dict(trade, account_id=1) for trade in trades if trade["is_prop"]],
                     datetime.now(NY).date())[0]
    prop["challenge"] = demo_challenge(prop)
    return {"dash": board, "calendar": month_calendar(trades, month),
            "equity_svg": equity_svg(board["equity"]), "trades": recent, "review": review, "prop": prop}
