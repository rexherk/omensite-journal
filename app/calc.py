"""P&L, R, and excursion math for one journaled trade.

An entry leg adds size in the trade's direction. An exit leg takes it off.
Fills are replayed in time order. R uses the average entry, the stop, and the
total size entered.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")


class TradeMathError(ValueError):
    """The legs cannot be turned into a position."""


@dataclass(frozen=True)
class Leg:
    kind: str
    qty: float
    price: float
    filled_at: datetime


@dataclass(frozen=True)
class TradeStats:
    gross_pnl: float
    net_pnl: float
    points: float | None
    ticks: float | None
    avg_entry: float | None
    avg_exit: float | None
    qty_entered: float
    qty_exited: float
    open_qty: float
    is_closed: bool
    opened_at: datetime | None
    closed_at: datetime | None
    hold_seconds: int | None
    risk_dollars: float | None
    r_multiple: float | None
    planned_r: float | None
    mae_points: float | None
    mfe_points: float | None
    mae_dollars: float | None
    mfe_dollars: float | None
    left_on_table: float | None
    session: str
    kill_zone: str
    macro_window: str


def summarize(
    *,
    direction: str,
    legs: list[Leg],
    stop: float | None,
    target: float | None,
    fees: float,
    point_value: float,
    tick: float,
    mae_price: float | None,
    mfe_price: float | None,
    session: str | None = None,
    kill_zone: str | None = None,
    macro_window: str | None = None,
) -> TradeStats:
    if direction not in {"long", "short"}:
        raise TradeMathError("Direction must be long or short.")
    if not legs:
        raise TradeMathError("Add at least one fill.")
    ordered = sorted(enumerate(legs), key=lambda item: (item[1].filled_at, item[0]))
    sign = 1.0 if direction == "long" else -1.0
    qty = 0.0
    avg = 0.0
    gross = 0.0
    entered = 0.0
    exited = 0.0
    exit_notional = 0.0
    opened: datetime | None = None
    closed_at: datetime | None = None

    for _, leg in ordered:
        if leg.kind not in {"entry", "exit"}:
            raise TradeMathError("Each fill is an entry or an exit.")
        if leg.qty <= 0 or leg.price <= 0:
            raise TradeMathError("Size and price have to be above zero.")
        if opened is None:
            opened = leg.filled_at
        if leg.kind == "entry":
            avg = ((avg * qty) + (leg.price * leg.qty)) / (qty + leg.qty) if qty else leg.price
            qty += leg.qty
            entered += leg.qty
            continue
        if leg.qty - qty > 1e-6:
            raise TradeMathError("An exit is larger than the open size at that time.")
        gross += (leg.price - avg) * leg.qty * point_value * sign
        qty -= leg.qty
        exited += leg.qty
        exit_notional += leg.price * leg.qty
        if qty <= 1e-6:
            qty = 0.0
            closed_at = leg.filled_at

    fees = max(0.0, float(fees or 0.0))
    net = gross - fees
    avg_exit = (exit_notional / exited) if exited else None
    points = ((gross / point_value) / exited) if exited and point_value else None
    ticks = (points / tick) if points is not None and tick else None
    risk = None
    actual_r = None
    planned = None
    if stop is not None and stop > 0 and avg and entered:
        risk_points = abs(avg - stop)
        if risk_points > 0:
            risk = risk_points * point_value * entered
            actual_r = net / risk
            if target is not None and target > 0:
                planned = abs(target - avg) / risk_points
    mae_pts, mfe_pts = _excursions(direction, avg if entered else None, mae_price, mfe_price)
    size_for_excursion = entered or qty
    mae_dol = mae_pts * point_value * size_for_excursion if mae_pts is not None else None
    mfe_dol = mfe_pts * point_value * size_for_excursion if mfe_pts is not None else None
    left = None
    if mfe_dol is not None and exited:
        left = max(0.0, mfe_dol - gross)
    hold = None
    if opened is not None and closed_at is not None:
        hold = max(0, int((closed_at - opened).total_seconds()))
    when = opened
    return TradeStats(
        gross_pnl=round(gross, 2),
        net_pnl=round(net, 2),
        points=None if points is None else round(points, 4),
        ticks=None if ticks is None else round(ticks, 2),
        avg_entry=None if not entered else round(avg, 6),
        avg_exit=None if avg_exit is None else round(avg_exit, 6),
        qty_entered=entered,
        qty_exited=exited,
        open_qty=round(qty, 6),
        is_closed=entered > 0 and qty <= 1e-6 and exited > 0,
        opened_at=opened,
        closed_at=closed_at if qty <= 1e-6 else None,
        hold_seconds=hold,
        risk_dollars=None if risk is None else round(risk, 2),
        r_multiple=None if actual_r is None else round(actual_r, 4),
        planned_r=None if planned is None else round(planned, 4),
        mae_points=None if mae_pts is None else round(mae_pts, 4),
        mfe_points=None if mfe_pts is None else round(mfe_pts, 4),
        mae_dollars=None if mae_dol is None else round(mae_dol, 2),
        mfe_dollars=None if mfe_dol is None else round(mfe_dol, 2),
        left_on_table=None if left is None else round(left, 2),
        session=session or session_for(when),
        kill_zone=kill_zone or kill_zone_for(when),
        macro_window=macro_window or macro_for(when),
    )


def grade_for(checked: int, total: int) -> str | None:
    if total <= 0:
        return None
    ratio = checked / total
    if ratio >= 1:
        return "A+"
    if ratio >= 0.8:
        return "A"
    if ratio >= 0.6:
        return "B"
    return "C"


def _excursions(
    direction: str,
    avg: float | None,
    mae_price: float | None,
    mfe_price: float | None,
) -> tuple[float | None, float | None]:
    if avg is None:
        return None, None
    mae = None
    mfe = None
    if mae_price is not None and mae_price > 0:
        mae = (avg - mae_price) if direction == "long" else (mae_price - avg)
        mae = max(0.0, mae)
    if mfe_price is not None and mfe_price > 0:
        mfe = (mfe_price - avg) if direction == "long" else (avg - mfe_price)
        mfe = max(0.0, mfe)
    return mae, mfe


def _ny_clock(moment: datetime | None) -> tuple[int, int] | None:
    if moment is None:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=NY)
    local = moment.astimezone(NY)
    return local.hour, local.minute


def _minutes(hour: int, minute: int) -> int:
    return hour * 60 + minute


def _in_window(hour: int, minute: int, start: tuple[int, int], end: tuple[int, int]) -> bool:
    value = _minutes(hour, minute)
    begin = _minutes(*start)
    finish = _minutes(*end)
    if begin <= finish:
        return begin <= value < finish
    return value >= begin or value < finish


def session_for(moment: datetime | None) -> str:
    """Map a fill onto Asia, London, NY AM, or NY PM in New York time."""
    clock = _ny_clock(moment)
    if clock is None:
        return "NY AM"
    if _in_window(*clock, (19, 0), (2, 0)):
        return "Asia"
    if _in_window(*clock, (2, 0), (8, 30)):
        return "London"
    if _in_window(*clock, (8, 30), (12, 0)):
        return "NY AM"
    return "NY PM"


def kill_zone_for(moment: datetime | None) -> str:
    clock = _ny_clock(moment)
    if clock is None:
        return "None"
    windows = [
        ((3, 0), (4, 0), "London Silver Bullet"),
        ((10, 0), (11, 0), "NY AM Silver Bullet"),
        ((14, 0), (15, 0), "NY PM Silver Bullet"),
        ((2, 0), (5, 0), "London Open"),
        ((8, 30), (11, 0), "NY AM"),
        ((13, 30), (16, 0), "NY PM"),
        ((20, 0), (0, 0), "Asia"),
    ]
    for start, end, name in windows:
        if _in_window(*clock, start, end):
            return name
    return "None"


def macro_for(moment: datetime | None) -> str:
    clock = _ny_clock(moment)
    if clock is None:
        return "None"
    windows = [
        ((2, 33), (3, 0), "02:33-03:00"),
        ((4, 3), (4, 30), "04:03-04:30"),
        ((9, 50), (10, 10), "09:50-10:10"),
        ((10, 50), (11, 10), "10:50-11:10"),
        ((11, 50), (12, 10), "11:50-12:10"),
        ((13, 10), (13, 40), "13:10-13:40"),
        ((15, 15), (15, 45), "15:15-15:45"),
    ]
    for start, end, name in windows:
        if _in_window(*clock, start, end):
            return name
    return "None"


def hold_label(seconds: int | None) -> str:
    if seconds is None:
        return "Open"
    minutes, _sec = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)
    if days:
        return f"{days}d {hours}h"
    if hours:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


def clock_in(moment: datetime, zone: ZoneInfo) -> datetime:
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=NY)
    return moment.astimezone(zone)


def week_start(day, zone: ZoneInfo):
    local = datetime.combine(day, time.min, zone)
    return (local - timedelta(days=local.weekday())).date()
