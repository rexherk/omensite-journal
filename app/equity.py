"""Dated equity and verified Topstep Combine rules for the dashboard.

Rule sources checked 2026-11-14:
https://help.topstep.com/en/articles/8284204-what-is-the-maximum-loss-limit
https://help.topstep.com/en/articles/8284208-consistency-at-topstep
https://help.topstep.com/en/articles/8284197-trading-combine-parameters
https://help.topstep.com/en/articles/15520357-topstep-labs
"""

from collections import defaultdict
from datetime import datetime, time, timedelta
from decimal import Decimal, ROUND_CEILING
from zoneinfo import ZoneInfo

UTC = ZoneInfo("UTC")
CT = ZoneInfo("America/Chicago")
TOPSTEP_EOD = "topstep-combine-eod-2026"
TOPSTEP_STATIC = "topstep-combine-static-50k-2026"
RULE_PROFILES = {
    TOPSTEP_EOD: "Topstep Trading Combine · end-of-day trailing",
    TOPSTEP_STATIC: "Topstep 50K Static Trading Combine",
}
RULE_SOURCES = [
    {"label": "Maximum Loss Limit", "url": "https://help.topstep.com/en/articles/8284204-what-is-the-maximum-loss-limit"},
    {"label": "Consistency target", "url": "https://help.topstep.com/en/articles/8284208-consistency-at-topstep"},
]
SIZE_RULES = {50000: (3000, 2000), 100000: (6000, 3000), 150000: (9000, 4500)}


def moment(stamp, zone=UTC):
    value = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    return value.replace(tzinfo=zone) if value.tzinfo is None else value


def combine_rules(account):
    """Require an explicit plan and matching saved settings, never a name match."""
    if not account or account["kind"] != "prop":
        return None, None
    profile = account.get("rule_profile")
    if profile not in RULE_PROFILES:
        return None, "Confirm this account’s plan and size in Settings to show its limits."
    size = account.get("starting_balance")
    expected = SIZE_RULES.get(size) if profile == TOPSTEP_EOD else {50000: (4000, 2000)}.get(size)
    if expected is None:
        return None, "This account size is not verified for the selected plan."
    target, loss = expected
    if (account.get("profit_target") != target or account.get("trailing_drawdown") != loss
            or account.get("consistency_pct") != 55
            or (profile == TOPSTEP_STATIC and account.get("daily_loss_limit") != 1000)):
        return None, "Saved limits differ from this plan’s verified rules. Review the account settings."
    return {
        "profile": profile, "label": RULE_PROFILES[profile], "size": size,
        "base_target": target, "loss_amount": loss, "consistency_pct": 55,
        "daily_loss_limit": account.get("daily_loss_limit"),
        "trailing": profile == TOPSTEP_EOD,
        "sources": RULE_SOURCES if profile == TOPSTEP_EOD else [
            {"label": "Static Combine rules", "url": "https://help.topstep.com/en/articles/15520357-topstep-labs"},
            RULE_SOURCES[1],
        ],
    }, None


def session_close(closed):
    local = closed.astimezone(CT)
    day = local.date() + timedelta(days=local.hour >= 17)
    return datetime.combine(day, time(15, 10), CT)


def adjusted_target(base, best_day, percentage):
    required = Decimal(str(best_day)) * 100 / Decimal(str(percentage))
    return float(max(Decimal(str(base)), required.quantize(Decimal(".01"), rounding=ROUND_CEILING)))


def equity_chart(trades, visible_ids, zone, account=None, since=None, now=None):
    """Use all account history for limits, retaining range-relative P&L.

    Drawdown is the realized decline from the full history's peak. Limit updates
    occur at the Topstep session close and are capped at the starting balance.
    Recorded closed fills cannot establish intratrade/unrealized compliance.
    """
    now = now or datetime.now(UTC)
    closed = sorted(
        (row for row in trades if row["is_closed"] and row.get("closed_at")
         and (account is None or row["account_id"] == account["id"])),
        key=lambda row: (moment(row["closed_at"]), row["id"]),
    )
    rules, warning = combine_rules(account)
    visible = [row for row in closed if row["id"] in visible_ids]
    result = {"timezone": str(zone), "account_id": account["id"] if account else None,
              "points": [], "limits": [], "rules": rules, "warning": warning,
              "net_pnl": 0, "drawdown": 0, "baseline": 0, "since": since.isoformat() if since else None}
    if not visible:
        return result
    start = max(moment(visible[0]["opened_at"]), datetime.combine(since, time.min, zone)) if since else moment(visible[0]["opened_at"])
    start = min(start, moment(visible[0]["closed_at"]))
    origin = sum(row["net_pnl"] or 0 for row in closed if row["id"] not in visible_ids
                 and moment(row["closed_at"]) < moment(visible[0]["closed_at"]))
    result["baseline"] = round(origin, 2)
    events = [(moment(row["closed_at"]), 0, row) for row in closed]
    if rules:
        settlements = {session_close(moment(row["closed_at"])) for row in closed}
        events.extend((stamp, 1, None) for stamp in settlements if stamp <= now)
    events.sort(key=lambda event: (event[0], event[1], event[2]["id"] if event[2] else 0))
    running = peak = best_day = 0
    floor = -rules["loss_amount"] if rules else None
    target = rules["base_target"] if rules else None
    day_net = defaultdict(float)
    initial_floor, initial_target = floor, target
    points, limits = [], []
    for stamp, settlement, trade in events:
        if settlement:
            best_day = max(best_day, day_net[stamp])
            if rules["trailing"]:
                floor = min(0, max(floor, running - rules["loss_amount"]))
            target = adjusted_target(rules["base_target"], best_day, rules["consistency_pct"])
        else:
            if trade["id"] == visible[0]["id"]:
                result["initial_drawdown"] = round(peak - running, 2)
            running = round(running + (trade["net_pnl"] or 0), 2)
            peak = max(peak, running)
            if rules:
                end = session_close(stamp)
                day_net[end] += trade["net_pnl"] or 0
                target = adjusted_target(rules["base_target"], max(best_day, day_net[end]), rules["consistency_pct"])
            if trade["id"] in visible_ids:
                local = stamp.astimezone(zone)
                points.append({
                    "id": trade["id"], "account_id": trade["account_id"], "instrument": trade["instrument"],
                    "time": int(stamp.timestamp() * 1000), "date": local.date().isoformat(),
                    "label": local.strftime("%b %d, %Y · %H:%M %Z"),
                    "trade_net": round(trade["net_pnl"] or 0, 2), "net": round(running - origin, 2),
                    "drawdown": round(peak - running, 2), "lifetime_net": running,
                    "floor": floor, "target": target,
                })
        if stamp < start:
            initial_floor, initial_target = floor, target
        elif rules:
            limits.append({"time": int(stamp.timestamp() * 1000),
                           "floor": round(floor - origin, 2), "target": round(target - origin, 2)})
    start_ms = int(start.timestamp() * 1000)
    result.update(points=points, net_pnl=points[-1]["net"], drawdown=points[-1]["drawdown"],
                  start=start_ms, end=max(points[-1]["time"], limits[-1]["time"] if limits else start_ms),
                  limits=([{"time": start_ms, "floor": round(initial_floor - origin, 2),
                            "target": round(initial_target - origin, 2)}] + limits) if rules else [])
    if rules:
        rules.update(current_floor=round(floor, 2), current_balance_floor=round(rules["size"] + floor, 2),
                     current_target=target, best_day=round(best_day, 2),
                     best_day_guideline=rules["base_target"] * rules["consistency_pct"] / 100)
    return result
