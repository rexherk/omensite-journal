"""One reproducible sample month for the public preview and read-only demo."""

from datetime import date, datetime, timedelta

from app.analytics import dashboard, month_calendar
from app.present import equity_svg


# Gross results in dollars, before the same $4.50 fee charged to each trade.
# Each row is one session; mixed outcomes give realistic daily win rates.
SESSIONS = (
    (-175, 112.5), (450,), (325, -125, 562.5), (875, -200),
    (-250, 137.5, -212.5), (325, 225), (162.5, -87.5, 287.5, 100),
    (525, -162.5, 350), (-225,), (700, -175, 437.5),
    (212.5, -112.5), (375,), (225, 187.5, -150, -100, 312.5),
    (537.5, -187.5, 262.5), (-287.5, 100), (650, 175),
    (262.5, -125, 150, 325), (-312.5, -137.5, 200),
    (487.5, 362.5), (550, -175, 237.5), (275,), (400, -125),
)


def sample_trades(today: date | None = None) -> list[dict]:
    """Use the last completed month; keep weekends and two weekdays trade-free."""
    today = today or date.today()
    end = today.replace(day=1) - timedelta(days=1)
    weekdays = [date(end.year, end.month, day) for day in range(1, end.day + 1)
                if date(end.year, end.month, day).weekday() < 5]
    active = [day for index, day in enumerate(weekdays) if index not in (5, 14)]
    records = []
    for session_index, day in enumerate(active):
        for slot, gross in enumerate(SESSIONS[session_index]):
            index = len(records)
            instrument, qty, multiplier, entry = (
                ("MES", 2, 5, 5800), ("NQ", 1, 20, 20125),
                ("ES", 1, 50, 5800), ("MNQ", 5, 2, 20125),
            )[index % 4]
            direction = "short" if index % 3 == 1 else "long"
            exit_price = entry + gross / (qty * multiplier) * (-1 if direction == "short" else 1)
            stamp = f"{day.isoformat()}T{9 + slot // 2:02d}:{35 + (slot % 2) * 20:02d}:00"
            net = gross - 4.5
            records.append({
                "id": index + 1, "instrument": instrument, "qty": qty,
                "direction": direction, "entry": entry, "exit": exit_price,
                "fees": 4.5, "is_closed": 1, "net_pnl": net,
                "opened_at": stamp, "closed_at": (datetime.fromisoformat(stamp) + timedelta(minutes=18 + index % 29)).isoformat(),
                "stop": entry + 250 / (qty * multiplier) * (1 if direction == "short" else -1),
                "r_multiple": net / 250, "followed_plan": int(net > 0 or index % 4 != 0),
                "left_on_table": 0, "session": "NY AM", "kill_zone": "NY AM",
                "grade": "A+" if net > 0 else "B", "emotion_before": "Calm" if net > 0 else "Anxious",
                "setup": ("Opening range", "Liquidity sweep", "Fair value gap", "Break & retest")[index % 4],
            })
    return records


def sample_overview(today: date | None = None) -> dict:
    trades = sample_trades(today)
    board = dashboard(trades, {})
    month = date.fromisoformat(trades[-1]["closed_at"][:10])
    return {"dash": board, "calendar": month_calendar(trades, month),
            "equity_svg": equity_svg(board["equity"]), "trades": list(reversed(trades))}
