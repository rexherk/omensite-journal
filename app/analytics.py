"""Dashboard numbers and plain-language notes from closed trades."""

from __future__ import annotations

from collections import defaultdict
import calendar
from datetime import date, timedelta


def dashboard(trades: list[dict], tags_by_trade: dict[int, list[str]]) -> dict:
    closed = [trade for trade in trades if trade["is_closed"]]
    closed.sort(key=lambda trade: trade["closed_at"] or "")
    wins = [trade for trade in closed if (trade["net_pnl"] or 0) > 0]
    losses = [trade for trade in closed if (trade["net_pnl"] or 0) < 0]
    gross_win = sum(trade["net_pnl"] for trade in wins)
    gross_loss = abs(sum(trade["net_pnl"] for trade in losses))
    rs = [trade["r_multiple"] for trade in closed if trade["r_multiple"] is not None]
    pnl = [trade["net_pnl"] or 0 for trade in closed]
    equity = _equity(closed)
    broken = [trade for trade in closed if trade["followed_plan"] == 0]
    left = sum(trade["left_on_table"] or 0 for trade in closed)
    return {
        "closed_count": len(closed),
        "open_count": sum(1 for trade in trades if not trade["is_closed"]),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": (len(wins) / len(closed)) if closed else None,
        "profit_factor": (gross_win / gross_loss) if gross_loss else None,
        "expectancy": (sum(pnl) / len(pnl)) if pnl else None,
        "average_r": (sum(rs) / len(rs)) if rs else None,
        "average_win": (gross_win / len(wins)) if wins else None,
        "average_loss": (sum(trade["net_pnl"] for trade in losses) / len(losses)) if losses else None,
        "net_pnl": sum(pnl),
        "max_drawdown": equity["max_drawdown"],
        "equity": equity["curve"],
        "streak": _streaks(closed),
        "rule_break_pnl": sum(trade["net_pnl"] or 0 for trade in broken),
        "rule_break_count": len(broken),
        "left_on_table": left,
        "by_session": _group(closed, lambda trade: trade["session"] or "Unset"),
        "by_kill_zone": _group(closed, lambda trade: trade["kill_zone"] or "None"),
        "by_weekday": _group(closed, lambda trade: _weekday(trade)),
        "by_hour": _group(closed, lambda trade: _hour(trade)),
        "by_instrument": _group(closed, lambda trade: trade["instrument"]),
        "by_direction": _group(closed, lambda trade: trade["direction"]),
        "by_grade": _group(closed, lambda trade: trade["grade"] or "Ungraded"),
        "by_emotion": _group(closed, lambda trade: trade["emotion_before"] or "Unset"),
        "by_concept": _group_tags(closed, tags_by_trade),
        "by_setup": _group(closed, lambda trade: (trade.get("setup") or "").strip() or "Unset"),
        "insights": _insights(closed, tags_by_trade),
        "heatmap": _heatmap(closed),
    }


def month_calendar(trades: list[dict], month: date) -> dict:
    """Dated cells and totals, calculated from closed trades only."""
    buckets = defaultdict(list)
    for trade in trades:
        if trade["is_closed"] and trade.get("closed_at"):
            buckets[trade["closed_at"][:10]].append(trade)
    days = []
    total = count = 0
    for week in calendar.Calendar(firstweekday=6).monthdatescalendar(month.year, month.month):
        for day in week:
            in_month = (day.year, day.month) == (month.year, month.month)
            records = buckets[day.isoformat()] if in_month else []
            pnl = round(sum(item["net_pnl"] or 0 for item in records), 2)
            total += pnl
            count += len(records)
            days.append({"date": day.isoformat(), "day": day.day, "in_month": in_month,
                         "pnl": pnl, "count": len(records),
                         "win_rate": sum((item["net_pnl"] or 0) > 0 for item in records) / len(records) if records else None})
    previous = month.replace(day=1) - timedelta(days=1)
    following = month.replace(day=28) + timedelta(days=4)
    return {"label": month.strftime("%B %Y"), "key": month.strftime("%Y-%m"),
            "previous": previous.strftime("%Y-%m"), "next": following.strftime("%Y-%m"),
            "days": days, "net_pnl": round(total, 2), "count": count}


def prop_rows(accounts: list[dict], trades: list[dict], today: date) -> list[dict]:
    rows = []
    for account in accounts:
        if account["kind"] != "prop":
            continue
        mine = [trade for trade in trades if trade["account_id"] == account["id"] and trade["is_closed"]]
        mine.sort(key=lambda trade: trade["closed_at"] or "")
        total = sum(trade["net_pnl"] or 0 for trade in mine)
        start = account["starting_balance"] or 0
        equity = start + total
        peak = start
        running = start
        for trade in mine:
            running += trade["net_pnl"] or 0
            peak = max(peak, running)
        drawdown = max(0.0, peak - equity)
        today_pnl = 0.0
        by_day: dict[str, float] = defaultdict(float)
        for trade in mine:
            closed = (trade["closed_at"] or "")[:10]
            if closed == today.isoformat():
                today_pnl += trade["net_pnl"] or 0
            if closed:
                by_day[closed] += trade["net_pnl"] or 0
        best_day = max(by_day.values()) if by_day else 0.0
        best_share = (best_day / total) if total > 0 else None
        limit = account["daily_loss_limit"]
        trail = account["trailing_drawdown"]
        target = account["profit_target"]
        rows.append(
            {
                "account": account,
                "equity": equity,
                "total_pnl": total,
                "today_pnl": today_pnl,
                "drawdown": drawdown,
                "daily_left": None if not limit else limit + today_pnl,
                "trail_left": None if not trail else trail - drawdown,
                "target_ratio": None if not target else total / target,
                "daily_hit": bool(limit and today_pnl <= -limit),
                "trail_hit": bool(trail and drawdown >= trail),
                "best_share": best_share,
                "consistency_pct": account.get("consistency_pct"),
            }
        )
    return rows


def review_slice(trades: list[dict], tags_by_trade: dict[int, list[str]], start: date, end: date) -> dict:
    chosen = []
    for trade in trades:
        if not trade["is_closed"] or not trade["closed_at"]:
            continue
        closed = date.fromisoformat(trade["closed_at"][:10])
        if start <= closed <= end:
            chosen.append(trade)
    ranked = sorted(chosen, key=lambda trade: trade["r_multiple"] if trade["r_multiple"] is not None else -999)
    mistakes: dict[str, int] = defaultdict(int)
    for trade in chosen:
        for tag in trade.get("mistakes", []):
            mistakes[tag] += 1
    best = list(reversed(ranked[-3:])) if ranked else []
    worst = ranked[:3] if ranked else []
    return {
        "trades": chosen,
        "net_pnl": sum(trade["net_pnl"] or 0 for trade in chosen),
        "count": len(chosen),
        "best": best,
        "worst": worst,
        "mistakes": sorted(mistakes.items(), key=lambda item: item[1], reverse=True)[:6],
        "adherence": _adherence(chosen),
    }


def _equity(trades: list[dict]) -> dict:
    running = 0.0
    peak = 0.0
    max_dd = 0.0
    curve = [{"label": "Start", "equity": 0.0}]
    for trade in trades:
        running += trade["net_pnl"] or 0
        peak = max(peak, running)
        max_dd = max(max_dd, peak - running)
        curve.append({"label": (trade["closed_at"] or "")[:10], "equity": round(running, 2)})
    return {"curve": curve, "max_drawdown": round(max_dd, 2)}


def _streaks(trades: list[dict]) -> dict:
    best_win = best_loss = current = 0
    current_kind = None
    for trade in trades:
        pnl = trade["net_pnl"] or 0
        if pnl == 0:
            current = 0
            current_kind = None
            continue
        kind = "win" if pnl > 0 else "loss"
        current = current + 1 if kind == current_kind else 1
        current_kind = kind
        if kind == "win":
            best_win = max(best_win, current)
        else:
            best_loss = max(best_loss, current)
    return {"win": best_win, "loss": best_loss, "current": current, "kind": current_kind}


def _group(trades: list[dict], key) -> list[dict]:
    buckets: dict[str, list[dict]] = defaultdict(list)
    for trade in trades:
        buckets[str(key(trade))].append(trade)
    return _finish(buckets)


def _group_tags(trades: list[dict], tags_by_trade: dict[int, list[str]]) -> list[dict]:
    buckets: dict[str, list[dict]] = defaultdict(list)
    for trade in trades:
        for tag in tags_by_trade.get(trade["id"], []):
            buckets[tag].append(trade)
    return _finish(buckets)


def _finish(buckets: dict[str, list[dict]]) -> list[dict]:
    rows = []
    for name, items in buckets.items():
        pnl = sum(trade["net_pnl"] or 0 for trade in items)
        wins = sum(1 for trade in items if (trade["net_pnl"] or 0) > 0)
        rs = [trade["r_multiple"] for trade in items if trade["r_multiple"] is not None]
        rows.append(
            {
                "name": name,
                "count": len(items),
                "pnl": pnl,
                "win_rate": wins / len(items) if items else 0,
                "average_r": (sum(rs) / len(rs)) if rs else None,
            }
        )
    rows.sort(key=lambda row: row["pnl"], reverse=True)
    peak = max((abs(row["pnl"]) for row in rows), default=0)
    for row in rows:
        row["bar"] = 0 if peak == 0 else round(abs(row["pnl"]) / peak * 100)
    return rows


def _insights(trades: list[dict], tags_by_trade: dict[int, list[str]]) -> list[str]:
    if len(trades) < 3:
        return ["Log at least three closed trades and the journal will compare your sessions, concepts, and grades."]
    lines: list[str] = []
    session_line = _contrast("session", _group(trades, lambda trade: trade["session"] or "Unset"))
    concept_rows = _group_tags(trades, tags_by_trade)
    concept_line = _contrast("concept", concept_rows)
    if session_line:
        lines.append(session_line)
    if concept_line:
        lines.append(concept_line)
    cross = _cross(trades, tags_by_trade)
    if cross:
        lines.append(cross)
    broken = [trade for trade in trades if trade["followed_plan"] == 0]
    cost = sum(trade["net_pnl"] or 0 for trade in broken)
    if broken and cost < 0:
        lines.append(
            f"Trades that broke the plan cost ${abs(cost):,.2f} across {len(broken)} trades."
        )
    elif broken:
        lines.append(f"{len(broken)} trades broke the plan and still netted ${cost:,.2f}.")
    left = sum(trade["left_on_table"] or 0 for trade in trades)
    if left > 0:
        lines.append(f"Exits gave back ${left:,.2f} versus the best price those trades reached.")
    grades = _group(trades, lambda trade: trade["grade"] or "Ungraded")
    grade_line = _contrast("grade", [row for row in grades if row["name"] != "Ungraded"])
    if grade_line:
        lines.append(grade_line)
    emotions = _group(trades, lambda trade: trade["emotion_before"] or "Unset")
    emotion_line = _contrast("emotion before entry", [row for row in emotions if row["name"] != "Unset"])
    if emotion_line:
        lines.append(emotion_line)
    setups = _group(trades, lambda trade: (trade.get("setup") or "").strip() or "Unset")
    setup_line = _contrast("setup", [row for row in setups if row["name"] != "Unset"])
    if setup_line:
        lines.append(setup_line)
    if not lines:
        lines.append(
            "No split stands out yet. A note shows up when two sessions, concepts, or grades each have at least three closed trades and point different ways."
        )
    return lines[:6]


def _contrast(label: str, rows: list[dict]) -> str | None:
    usable = [row for row in rows if row["count"] >= 3 and row["average_r"] is not None]
    if len(usable) < 2:
        return None
    best = max(usable, key=lambda row: row["average_r"])
    worst = min(usable, key=lambda row: row["average_r"])
    if best["name"] == worst["name"] or best["average_r"] <= 0 or worst["pnl"] >= 0:
        return None
    return (
        f"Your {best['name']} {label} trades average {best['average_r']:+.2f}R. "
        f"{worst['name']} trades are down ${abs(worst['pnl']):,.2f}."
    )


def _cross(trades: list[dict], tags_by_trade: dict[int, list[str]]) -> str | None:
    buckets: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for trade in trades:
        for tag in tags_by_trade.get(trade["id"], []):
            buckets[(trade["session"] or "Unset", tag)].append(trade)
    best = None
    for (session, tag), items in buckets.items():
        rs = [trade["r_multiple"] for trade in items if trade["r_multiple"] is not None]
        if len(items) < 3 or not rs:
            continue
        avg = sum(rs) / len(rs)
        if best is None or avg > best[0]:
            best = (avg, session, tag, len(items))
    if best is None or best[0] <= 0:
        return None
    avg, session, tag, count = best
    return f"Your {session} {tag} trades average {avg:+.2f}R across {count} trades."


def _heatmap(trades: list[dict]) -> list[dict]:
    totals: dict[str, float] = defaultdict(float)
    for trade in trades:
        if trade["closed_at"]:
            totals[trade["closed_at"][:10]] += trade["net_pnl"] or 0
    if not totals:
        return []
    end = date.fromisoformat(max(totals))
    start = end - timedelta(days=end.weekday() + 7 * 15)
    peak = max((abs(value) for value in totals.values()), default=1) or 1
    weeks = []
    cursor = start
    while cursor <= end:
        days = []
        for offset in range(7):
            day = cursor + timedelta(days=offset)
            value = totals.get(day.isoformat(), 0.0) if day <= end else None
            tone = "flat"
            if value is None:
                tone = "empty"
            elif value > 0:
                tone = "up"
            elif value < 0:
                tone = "down"
            strength = 0 if not value else min(1.0, abs(value) / peak)
            days.append({"date": day.isoformat(), "pnl": value, "tone": tone, "strength": round(strength, 3)})
        weeks.append(days)
        cursor += timedelta(days=7)
    return weeks


def _weekday(trade: dict) -> str:
    if not trade["closed_at"]:
        return "Unset"
    return date.fromisoformat(trade["closed_at"][:10]).strftime("%A")


def _hour(trade: dict) -> str:
    stamp = trade["opened_at"] or ""
    if len(stamp) < 13:
        return "Unset"
    return stamp[11:13] + ":00"


def _adherence(trades: list[dict]) -> float | None:
    answered = [trade for trade in trades if trade["followed_plan"] in (0, 1)]
    if not answered:
        return None
    return sum(1 for trade in answered if trade["followed_plan"] == 1) / len(answered)
