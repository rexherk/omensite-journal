"""Turn forms, CSV rows, and the sample journal into saved trades."""

from __future__ import annotations

import base64
import csv
import io
import json
import math
import re
import sqlite3
import time
from datetime import date, datetime, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.analytics import dashboard, month_calendar, prop_rows, review_slice
from app.auth import hash_password, new_token, verify_password
from app.calc import Leg, TradeMathError, grade_for, hold_label, summarize
from app.catalog import (
    ACCOUNT_KINDS,
    BIASES,
    DEFAULT_CHECKS,
    DRAWS,
    EMOTIONS,
    GRADES,
    KILL_ZONES,
    MACROS,
    MARKUP_COLORS,
    MISTAKES,
    PREMIUM,
    SESSIONS,
    SHOT_SLOTS,
    TAGS,
)
from app.imports import ImportError as CsvImportError
from app.imports import parse_csv
from app.instruments import future_root, parse_symbol, spec_for
from app.news_data import CAVEAT
from app.paths import import_dir, upload_path
from app.present import equity_svg
from app.sample_data import (
    CHALLENGE_END, CHALLENGE_START, DEMO_EMAIL, DEMO_FUNDED_NAME, DEMO_NOTE, DEMO_PROP,
    FORMER_DEMO_PROP_NAMES, LEGACY_DEMO_PROP, demo_challenge, demo_trade_plan, sample_trades,
)
from app.services_error import JournalError
from app import db

UTC = ZoneInfo("UTC")
NY = ZoneInfo("America/New_York")
SAMPLE_NOTE = "Sample journal entry"
_TOKEN = re.compile(r"[A-Za-z0-9_-]{8,80}")
# Existing saved annotations and backups retain their original colors.
_COLORS = set(MARKUP_COLORS) | {"#d7b56d", "#e08b7d", "#7dcea0", "#e7e4dc", "#8eb4e8"}
_BREAKDOWNS = [
    ("Session", "by_session"),
    ("Kill zone", "by_kill_zone"),
    ("Weekday", "by_weekday"),
    ("Hour", "by_hour"),
    ("Instrument", "by_instrument"),
    ("Long / short", "by_direction"),
    ("Grade", "by_grade"),
    ("Emotion before", "by_emotion"),
    ("ICT concept", "by_concept"),
    ("Setup", "by_setup"),
]


def user_zone(user: dict) -> ZoneInfo:
    try:
        return ZoneInfo(user["timezone"])
    except (ZoneInfoNotFoundError, KeyError, TypeError):
        return NY


def utc_iso(moment: datetime) -> str:
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def local_stamp(moment: datetime, zone: ZoneInfo) -> str:
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=zone)
    return moment.astimezone(zone).strftime("%Y-%m-%dT%H:%M:%S")


def parse_iso(text: str) -> datetime:
    raw = (text or "").strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    moment = datetime.fromisoformat(raw)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return moment


def show_time(iso: str | None, zone: ZoneInfo) -> str:
    if not iso:
        return "—"
    return parse_iso(iso).astimezone(zone).strftime("%b %d, %Y %H:%M")


def form_time(iso: str, zone: ZoneInfo) -> str:
    return parse_iso(iso).astimezone(zone).strftime("%Y-%m-%dT%H:%M")


def clean_email(raw: str) -> str:
    email = (raw or "").strip().lower()
    if " " in email or email.count("@") != 1 or not 3 <= len(email) <= 120:
        raise JournalError("Enter a valid email.")
    name, domain = email.split("@")
    if not name or "." not in domain or domain.startswith(".") or domain.endswith("."):
        raise JournalError("Enter a valid email.")
    return email


def _provision(conn, email: str, password: str, discord_id: str | None, display_name: str | None) -> int:
    salt, digest = hash_password(password)
    user_id = db.create_user(conn, email, salt, digest, "America/New_York")
    if discord_id:
        db.attach_discord(conn, user_id, discord_id, display_name or "")
    db.insert_account(conn, user_id, "Personal", "personal", 0, None, None, None)
    db.insert_account(conn, user_id, "Sim", "sim", 100000, None, None, None)
    for index, label in enumerate(DEFAULT_CHECKS):
        db.add_check(conn, user_id, label, index)
    return user_id


def register_user(conn, email: str, password: str) -> int:
    email = clean_email(email)
    if email == "demo@omensite.journal":
        raise JournalError("That email is reserved for the demo. Use your own email.")
    if len(password or "") < 8:
        raise JournalError("Use at least 8 characters.")
    if db.user_by_email(conn, email):
        raise JournalError("An account with that email already exists.")
    return _provision(conn, email, password, None, None)


def discord_display(profile: dict) -> str:
    raw = str(profile.get("global_name") or profile.get("username") or "").strip()
    cleaned = "".join(ch for ch in raw if ch.isprintable())
    return cleaned[:80] or "Discord"


def login_discord(conn, profile: dict) -> int:
    discord_id = str(profile.get("id") or "").strip()
    if not discord_id.isdigit() or not 5 <= len(discord_id) <= 32:
        raise JournalError("Discord did not return a usable account.")
    name = discord_display(profile)
    found = db.user_by_discord(conn, discord_id)
    if found:
        db.attach_discord(conn, found["id"], discord_id, name)
        return int(found["id"])
    email = ""
    if profile.get("verified") and profile.get("email"):
        email = clean_email(str(profile["email"]))
    if not email:
        email = f"{discord_id}@users.discord.local"
    existing = db.user_by_email(conn, email)
    if existing:
        linked = str(existing.get("discord_id") or "")
        if linked and linked != discord_id:
            raise JournalError("That email already belongs to another journal.")
        db.attach_discord(conn, existing["id"], discord_id, name)
        return int(existing["id"])
    user_id = _provision(conn, email, new_token(), discord_id, name)
    db.set_onboarded(conn, user_id, 0)
    return user_id


def login_google(conn, profile: dict) -> int:
    google_id = str(profile.get("id") or "").strip()
    if not google_id or len(google_id) > 80:
        raise JournalError("Google did not return a usable account.")
    name = discord_display({"global_name": profile.get("name") or profile.get("email") or "Google"})
    found = db.user_by_google(conn, google_id)
    if found:
        db.attach_google(conn, found["id"], google_id, name)
        return int(found["id"])
    email = ""
    if profile.get("verified_email") and profile.get("email"):
        email = clean_email(str(profile["email"]))
    if not email:
        safe = "".join(ch for ch in google_id if ch.isalnum())[:40] or "account"
        email = f"{safe}@users.google.local"
    existing = db.user_by_email(conn, email)
    if existing:
        linked = str(existing.get("google_id") or "")
        if linked and linked != google_id:
            raise JournalError("That email already belongs to another journal.")
        db.attach_google(conn, existing["id"], google_id, name)
        return int(existing["id"])
    user_id = _provision(conn, email, new_token(), None, None)
    db.attach_google(conn, user_id, google_id, name)
    db.set_onboarded(conn, user_id, 0)
    return user_id


def authenticate(conn, email: str, password: str) -> dict | None:
    try:
        cleaned = clean_email(email)
    except JournalError:
        return None
    row = db.user_by_email(conn, cleaned)
    if row is None or not verify_password(password or "", row["password_salt"], row["password_hash"]):
        return None
    return row


def start_session(conn, user_id: int) -> str:
    token = new_token()
    csrf = new_token()
    expires = utc_iso(datetime.now(UTC) + timedelta(days=14))
    db.create_session(conn, user_id, token, csrf, expires)
    return token


def update_profile(conn, user: dict, timezone: str, window_text: str) -> None:
    try:
        zone = ZoneInfo((timezone or "").strip())
    except ZoneInfoNotFoundError as exc:
        raise JournalError("Choose a timezone from the list.") from exc
    try:
        window = int(str(window_text).strip())
    except ValueError as exc:
        raise JournalError("The news window is a number of minutes.") from exc
    if window < 1 or window > 180:
        raise JournalError("The news window is between 1 and 180 minutes.")
    db.update_user(conn, user["id"], str(zone), window)


def _one(form, key: str) -> str:
    value = form.get(key) if form is not None else None
    return "" if value is None else str(value)


def _values(form, key: str) -> list[str]:
    if hasattr(form, "getlist"):
        return [str(item) for item in form.getlist(key)]
    value = form.get(key) if form is not None else None
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(value)]


def _choice(text: str, allowed: list[str], label: str) -> str:
    value = (text or "").strip()
    if not value:
        return ""
    if value not in allowed:
        raise JournalError(f"{label} is not one of the journal's choices.")
    return value


def _clip(text: str, label: str, limit: int) -> str:
    value = (text or "").strip()
    if len(value) > limit:
        raise JournalError(f"{label} is limited to {limit} characters.")
    return value


def _number(text: str, label: str, *, allow_zero: bool = False) -> float | None:
    raw = (text or "").strip().replace(",", "").replace("$", "")
    if raw == "":
        return None
    try:
        value = float(raw)
    except ValueError as exc:
        raise JournalError(f"{label} must be a number.") from exc
    if not math.isfinite(value):
        raise JournalError(f"{label} must be a number.")
    if allow_zero:
        if value < 0:
            raise JournalError(f"{label} cannot be negative.")
        return value
    if value <= 0:
        raise JournalError(f"{label} has to be above zero.")
    return value


def _parse_clock(text: str, zone: ZoneInfo) -> datetime:
    raw = (text or "").strip()
    if not raw:
        raise JournalError("Each fill needs a time.")
    for fmt in ("%Y-%m-%dT%H:%M", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(raw, fmt).replace(tzinfo=zone)
        except ValueError:
            continue
    raise JournalError(f"Could not read the time {text}.")


def blank_draft(account_id="") -> dict:
    return {
        "instrument": "",
        "asset_class": "future",
        "direction": "long",
        "account_id": str(account_id or ""),
        "fees": "0",
        "stop": "",
        "target": "",
        "mae": "",
        "mfe": "",
        "session": "",
        "kill_zone": "",
        "macro": "",
        "htf_bias": "",
        "draw": "",
        "premium": "",
        "range_high": "",
        "range_low": "",
        "setup": "",
        "went_right": "",
        "went_wrong": "",
        "lesson": "",
        "notes": "",
        "emotion_before": "",
        "emotion_after": "",
        "confidence": "",
        "followed_plan": "",
        "grade_override": "",
        "legs": [
            {"kind": "entry", "qty": "", "price": "", "time": ""},
            {"kind": "entry", "qty": "", "price": "", "time": ""},
            {"kind": "exit", "qty": "", "price": "", "time": ""},
            {"kind": "exit", "qty": "", "price": "", "time": ""},
        ],
        "tags": [],
        "mistakes": [],
        "checks": [],
    }


def draft_from_form(form) -> dict:
    draft = blank_draft()
    for key in (
        "instrument", "asset_class", "direction", "account_id", "fees", "stop", "target",
        "mae", "mfe", "session", "kill_zone", "macro", "htf_bias", "draw", "premium",
        "range_high", "range_low", "setup", "went_right", "went_wrong", "lesson", "notes",
        "emotion_before", "emotion_after", "confidence", "followed_plan", "grade_override",
    ):
        draft[key] = _one(form, key)
    kinds = _values(form, "leg_kind")
    qtys = _values(form, "leg_qty")
    prices = _values(form, "leg_price")
    times = _values(form, "leg_time")
    count = max(len(kinds), len(qtys), len(prices), len(times))
    if count:
        draft["legs"] = []
        for index in range(count):
            draft["legs"].append(
                {
                    "kind": kinds[index] if index < len(kinds) and kinds[index] in {"entry", "exit"} else "entry",
                    "qty": qtys[index] if index < len(qtys) else "",
                    "price": prices[index] if index < len(prices) else "",
                    "time": times[index] if index < len(times) else "",
                }
            )
    draft["tags"] = [tag for tag in _values(form, "tags") if tag in TAGS]
    draft["mistakes"] = [tag for tag in _values(form, "mistakes") if tag in MISTAKES]
    draft["checks"] = [int(item) for item in _values(form, "checks") if str(item).isdigit()]
    return draft


def draft_from_trade(trade: dict, legs: list[dict], tags: list[str], mistakes: list[str], checks: list[dict], zone: ZoneInfo) -> dict:
    draft = blank_draft(trade["account_id"])
    draft.update(
        {
            "instrument": trade["instrument"],
            "asset_class": trade["asset_class"],
            "direction": trade["direction"],
            "fees": _plain(trade["fees"]),
            "stop": _plain(trade["stop"]),
            "target": _plain(trade["target"]),
            "mae": _plain(trade["mae_price"]),
            "mfe": _plain(trade["mfe_price"]),
            "session": trade["session"] or "",
            "kill_zone": trade["kill_zone"] or "",
            "macro": trade["macro_window"] or "",
            "htf_bias": trade["htf_bias"] or "",
            "draw": trade["draw"] or "",
            "premium": trade["premium"] or "",
            "range_high": _plain(trade["range_high"]),
            "range_low": _plain(trade["range_low"]),
            "setup": trade["setup"] or "",
            "went_right": trade["went_right"] or "",
            "went_wrong": trade["went_wrong"] or "",
            "lesson": trade["lesson"] or "",
            "notes": trade["notes"] or "",
            "emotion_before": trade["emotion_before"] or "",
            "emotion_after": trade["emotion_after"] or "",
            "confidence": "" if trade["confidence"] is None else str(trade["confidence"]),
            "followed_plan": "yes" if trade["followed_plan"] == 1 else "no" if trade["followed_plan"] == 0 else "",
            "grade_override": trade["grade"] if trade["grade_manual"] else "",
            "tags": list(tags),
            "mistakes": list(mistakes),
            "checks": [row["item_id"] for row in checks if row["checked"]],
        }
    )
    draft["legs"] = [
        {
            "kind": leg["kind"],
            "qty": _plain(leg["qty"]),
            "price": _plain(leg["price"]),
            "time": form_time(leg["filled_at"], zone),
        }
        for leg in legs
    ]
    draft["legs"].append({"kind": "exit", "qty": "", "price": "", "time": ""})
    return draft


def _plain(value) -> str:
    if value is None or value == "":
        return ""
    return f"{float(value):.6f}".rstrip("0").rstrip(".")


def checklist_for_form(items: list[dict], previous: list[dict]) -> list[dict]:
    previous_ids = {row["item_id"] for row in previous}
    return [item for item in items if item["active"] or item["id"] in previous_ids]


def compose(
    *,
    zone: ZoneInfo,
    instrument: str,
    asset_class: str,
    direction: str,
    fees: float,
    legs: list[Leg],
    account_id: int,
    stop: float | None = None,
    target: float | None = None,
    mae: float | None = None,
    mfe: float | None = None,
    session: str | None = None,
    kill_zone: str | None = None,
    macro_window: str | None = None,
    htf_bias: str = "",
    draw: str = "",
    premium: str = "",
    range_high: float | None = None,
    range_low: float | None = None,
    setup: str = "",
    grade: str | None = None,
    auto_grade: str | None = None,
    grade_manual: int = 0,
    went_right: str = "",
    went_wrong: str = "",
    lesson: str = "",
    notes: str = "",
    emotion_before: str = "",
    emotion_after: str = "",
    confidence: int | None = None,
    followed_plan: int | None = None,
) -> tuple[dict, list[dict]]:
    if direction not in {"long", "short"}:
        raise JournalError("Direction is long or short.")
    if not legs:
        raise JournalError("Add at least one fill.")
    ordered = [item[1] for item in sorted(enumerate(legs), key=lambda pair: (pair[1].filled_at, pair[0]))]
    if ordered[0].kind != "entry":
        raise JournalError("The earliest fill has to be an entry.")
    try:
        spec = spec_for(asset_class, instrument)
    except ValueError as exc:
        raise JournalError(str(exc)) from exc
    try:
        stats = summarize(
            direction=direction,
            legs=ordered,
            stop=stop,
            target=target,
            fees=fees,
            point_value=spec.point_value,
            tick=spec.tick,
            mae_price=mae,
            mfe_price=mfe,
            session=session or None,
            kill_zone=kill_zone or None,
            macro_window=macro_window or None,
        )
    except TradeMathError as exc:
        raise JournalError(str(exc)) from exc
    fields = {
        "account_id": account_id,
        "instrument": spec.symbol,
        "asset_class": spec.asset_class,
        "direction": direction,
        "fees": round(float(fees or 0), 2),
        "stop": stop,
        "target": target,
        "session": stats.session,
        "kill_zone": stats.kill_zone,
        "macro_window": stats.macro_window,
        "htf_bias": htf_bias,
        "draw": draw,
        "premium": premium,
        "range_high": range_high,
        "range_low": range_low,
        "setup": setup,
        "grade": grade,
        "auto_grade": auto_grade,
        "grade_manual": 1 if grade_manual else 0,
        "went_right": went_right,
        "went_wrong": went_wrong,
        "lesson": lesson,
        "notes": notes,
        "emotion_before": emotion_before,
        "emotion_after": emotion_after,
        "confidence": confidence,
        "followed_plan": followed_plan,
        "mae_price": mae,
        "mfe_price": mfe,
        "opened_at": utc_iso(stats.opened_at) if stats.opened_at else None,
        "closed_at": utc_iso(stats.closed_at) if stats.closed_at else None,
        "opened_local": local_stamp(stats.opened_at, zone) if stats.opened_at else None,
        "closed_local": local_stamp(stats.closed_at, zone) if stats.closed_at else None,
        "closed_day": local_stamp(stats.closed_at, zone)[:10] if stats.closed_at else None,
        "is_closed": 1 if stats.is_closed else 0,
        "net_pnl": stats.net_pnl,
        "gross_pnl": stats.gross_pnl,
        "points": stats.points,
        "ticks": stats.ticks,
        "r_multiple": stats.r_multiple,
        "planned_r": stats.planned_r,
        "hold_seconds": stats.hold_seconds,
        "risk_dollars": stats.risk_dollars,
        "mae_points": stats.mae_points,
        "mfe_points": stats.mfe_points,
        "mae_dollars": stats.mae_dollars,
        "mfe_dollars": stats.mfe_dollars,
        "left_on_table": stats.left_on_table,
        "avg_entry": stats.avg_entry,
        "avg_exit": stats.avg_exit,
        "qty_entered": stats.qty_entered,
        "qty_exited": stats.qty_exited,
        "open_qty": stats.open_qty,
    }
    leg_rows = [
        {"kind": leg.kind, "qty": leg.qty, "price": leg.price, "filled_at": utc_iso(leg.filled_at)}
        for leg in ordered
    ]
    return fields, leg_rows


def parse_trade_form(form, zone: ZoneInfo, shown: list[dict]) -> dict:
    asset = _one(form, "asset_class").strip().lower()
    if asset not in {"future", "stock"}:
        raise JournalError("Choose futures or stock.")
    direction = _one(form, "direction").strip().lower()
    if direction not in {"long", "short"}:
        raise JournalError("Direction is long or short.")
    account_raw = _one(form, "account_id").strip()
    if not account_raw.isdigit():
        raise JournalError("Choose an account.")
    fees = _number(_one(form, "fees"), "Fees", allow_zero=True) or 0
    high = _number(_one(form, "range_high"), "Dealing range high")
    low = _number(_one(form, "range_low"), "Dealing range low")
    if high is not None and low is not None and high < low:
        raise JournalError("The dealing range high is below the low.")
    confidence_raw = _one(form, "confidence").strip()
    confidence = None
    if confidence_raw:
        if not confidence_raw.isdigit() or not 1 <= int(confidence_raw) <= 10:
            raise JournalError("Confidence is a number from 1 to 10.")
        confidence = int(confidence_raw)
    plan_raw = _one(form, "followed_plan").strip().lower()
    if plan_raw == "yes":
        followed = 1
    elif plan_raw == "no":
        followed = 0
    elif plan_raw == "":
        followed = None
    else:
        raise JournalError("Followed the plan is yes, no, or blank.")
    kinds = _values(form, "leg_kind")
    qtys = _values(form, "leg_qty")
    prices = _values(form, "leg_price")
    times = _values(form, "leg_time")
    count = max(len(kinds), len(qtys), len(prices), len(times))
    legs: list[Leg] = []
    for index in range(count):
        qty_text = qtys[index] if index < len(qtys) else ""
        price_text = prices[index] if index < len(prices) else ""
        time_text = times[index] if index < len(times) else ""
        if not (qty_text.strip() or price_text.strip() or time_text.strip()):
            continue
        kind = kinds[index] if index < len(kinds) else "entry"
        if kind not in {"entry", "exit"}:
            raise JournalError("Each fill is an entry or an exit.")
        qty = _number(qty_text, "Size")
        price = _number(price_text, "Price")
        if qty is None or price is None:
            raise JournalError("Each fill needs a size, a price, and a time.")
        legs.append(Leg(kind, qty, price, _parse_clock(time_text, zone)))
    if len(legs) > 40:
        raise JournalError("A trade is limited to 40 fills.")
    posted = {int(item) for item in _values(form, "checks") if str(item).isdigit()}
    check_rows = []
    checked = 0
    for item in shown:
        flag = 1 if item["id"] in posted else 0
        checked += flag
        check_rows.append({"item_id": item["id"], "checked": flag})
    auto = grade_for(checked, len(check_rows))
    picked = _choice(_one(form, "grade_override"), GRADES, "Grade")
    fields, leg_rows = compose(
        zone=zone,
        instrument=_one(form, "instrument"),
        asset_class=asset,
        direction=direction,
        fees=fees,
        legs=legs,
        account_id=int(account_raw),
        stop=_number(_one(form, "stop"), "Stop"),
        target=_number(_one(form, "target"), "Target"),
        mae=_number(_one(form, "mae"), "MAE price"),
        mfe=_number(_one(form, "mfe"), "MFE price"),
        session=_choice(_one(form, "session"), SESSIONS, "Session") or None,
        kill_zone=_choice(_one(form, "kill_zone"), KILL_ZONES, "Kill zone") or None,
        macro_window=_choice(_one(form, "macro"), MACROS, "Macro") or None,
        htf_bias=_choice(_one(form, "htf_bias"), BIASES, "HTF bias"),
        draw=_choice(_one(form, "draw"), DRAWS, "Draw on liquidity"),
        premium=_choice(_one(form, "premium"), PREMIUM, "Premium or discount"),
        range_high=high,
        range_low=low,
        setup=_clip(_one(form, "setup"), "Setup", 80),
        grade=picked or auto,
        auto_grade=auto,
        grade_manual=1 if picked else 0,
        went_right=_clip(_one(form, "went_right"), "What went right", 4000),
        went_wrong=_clip(_one(form, "went_wrong"), "What went wrong", 4000),
        lesson=_clip(_one(form, "lesson"), "Lesson", 4000),
        notes=_clip(_one(form, "notes"), "Notes", 4000),
        emotion_before=_choice(_one(form, "emotion_before"), EMOTIONS, "Emotion before"),
        emotion_after=_choice(_one(form, "emotion_after"), EMOTIONS, "Emotion after"),
        confidence=confidence,
        followed_plan=followed,
    )
    tags = [tag for tag in TAGS if tag in set(_values(form, "tags"))]
    mistakes = [tag for tag in MISTAKES if tag in set(_values(form, "mistakes"))]
    return {"trade": fields, "legs": leg_rows, "tags": tags, "mistakes": mistakes, "checks": check_rows}


def save_trade(conn, user_id: int, parsed: dict, trade_id: int | None = None) -> int:
    account_id = parsed["trade"]["account_id"]
    if db.account(conn, user_id, account_id) is None:
        raise JournalError("Choose an account.")
    owned = {item["id"] for item in db.checklist(conn, user_id)}
    for item in parsed["checks"]:
        if item["item_id"] not in owned:
            raise JournalError("A checklist item is not on your list.")
    fields = parsed["trade"]
    if trade_id is None:
        stored = dict(fields)
        stored["user_id"] = user_id
        stored["created_at"] = utc_iso(datetime.now(UTC))
        trade_id = db.insert_trade(conn, stored)
    elif not db.update_trade(conn, user_id, trade_id, fields):
        raise JournalError("Trade not found.")
    db.replace_children(conn, trade_id, parsed["legs"], parsed["tags"], parsed["mistakes"], parsed["checks"])
    return trade_id


def remove_trade(conn, user_id: int, trade_id: int) -> None:
    if db.trade(conn, user_id, trade_id) is None:
        raise JournalError("Trade not found.")
    names = [shot["filename"] for shot in db.shots(conn, trade_id)]
    if not db.delete_trade(conn, user_id, trade_id):
        raise JournalError("Trade not found.")
    for name in names:
        delete_image(conn, user_id, name)


def _math_rows(trades: list[dict], mistakes: dict[int, list[str]]) -> list[dict]:
    rows = []
    for trade in trades:
        view = dict(trade)
        if trade.get("opened_local"):
            view["opened_at"] = trade["opened_local"]
        if trade.get("closed_local"):
            view["closed_at"] = trade["closed_local"]
        view["mistakes"] = mistakes.get(trade["id"], [])
        rows.append(view)
    return rows


def news_near(opened_iso: str | None, events: list[dict], minutes: int) -> list[dict]:
    if not opened_iso:
        return []
    opened = parse_iso(opened_iso)
    window = max(0, int(minutes)) * 60
    found = []
    for event in events:
        if event["impact"] != "high" or event["category"] != "economic":
            continue
        delta = abs((opened - parse_iso(event["when_utc"])).total_seconds())
        if delta <= window:
            found.append(
                {
                    "title": event["title"],
                    "minutes": int(round(delta / 60)),
                    "when_utc": event["when_utc"],
                }
            )
    found.sort(key=lambda item: (item["minutes"], item["title"]))
    return found


def decorate_trades(conn, user: dict) -> list[dict]:
    zone = user_zone(user)
    events = db.news_events(conn)
    tags = db.tags_for_user(conn, user["id"])
    mistakes = db.mistakes_for_user(conn, user["id"])
    window = int(user["news_window_minutes"])
    rows = []
    for trade in db.trades(conn, user["id"]):
        row = dict(trade)
        row["when"] = show_time(row.get("opened_at"), zone)
        row["closed_label"] = show_time(row.get("closed_at"), zone)
        row["tags"] = tags.get(row["id"], [])
        row["mistakes"] = mistakes.get(row["id"], [])
        row["news"] = news_near(row.get("opened_at"), events, window)
        row["hold_label"] = hold_label(row.get("hold_seconds"))
        rows.append(row)
    return rows


def next_high_impact(conn, now: datetime | None = None) -> dict | None:
    moment = now or datetime.now(UTC)
    found = None
    found_when = None
    for event in db.news_events(conn):
        if event["impact"] != "high" or event["category"] != "economic":
            continue
        when = parse_iso(event["when_utc"])
        if when < moment:
            continue
        if found_when is None or when < found_when:
            found = event
            found_when = when
    if found is None or found_when is None:
        return None
    minutes = max(0, int(round((found_when - moment).total_seconds() / 60)))
    if minutes >= 1440:
        when_label = f"in {minutes // 1440}d {(minutes % 1440) // 60}h"
    elif minutes >= 60:
        when_label = f"in {minutes // 60}h {minutes % 60}m"
    else:
        when_label = f"in {minutes} min"
    return {
        "title": found["title"],
        "when_utc": found["when_utc"],
        "minutes": minutes,
        "when_label": when_label,
    }


def begin_reset(conn, email: str) -> str | None:
    try:
        cleaned = clean_email(email)
    except JournalError:
        return None
    user = db.user_by_email(conn, cleaned)
    if user is None:
        return None
    token = new_token()
    expires = utc_iso(datetime.now(UTC) + timedelta(minutes=30))
    db.create_reset(conn, user["id"], token, expires)
    return token


def complete_reset(conn, token: str, password: str) -> None:
    if len(password or "") < 8:
        raise JournalError("Use at least 8 characters.")
    row = db.reset_row(conn, token)
    if row is None:
        raise JournalError("That reset link is no longer valid.")
    expires = parse_iso(row["expires_at"])
    if expires < datetime.now(UTC):
        db.delete_reset(conn, token)
        raise JournalError("That reset link is no longer valid.")
    salt, digest = hash_password(password)
    db.set_password(conn, row["user_id"], salt, digest)
    db.delete_reset(conn, token)


def _demo_trades_without_plan(conn, user_id: int) -> list[dict]:
    return db.many(
        conn,
        """SELECT id, instrument, direction, avg_entry, qty_entered, opened_at, net_pnl
           FROM trades WHERE user_id = ? AND notes = ?
           AND (target IS NULL OR planned_r IS NULL OR planned_r <> 2)""",
        (user_id, DEMO_NOTE),
    )


def demo_needs_refresh(conn, user_id: int, through: date) -> bool:
    if db.sample_count(conn, user_id, DEMO_NOTE) < len(sample_trades(through)) or _demo_trades_without_plan(conn, user_id):
        return True
    names = {row["name"] for row in db.accounts(conn, user_id)}
    return DEMO_FUNDED_NAME not in names or not names.isdisjoint(FORMER_DEMO_PROP_NAMES)


def open_demo(conn, through: date) -> int:
    db.lock_demo_seed(conn)
    user = db.user_by_email(conn, DEMO_EMAIL)
    if user is None:
        user_id = _provision(conn, DEMO_EMAIL, new_token(), None, None)
        db.set_onboarded(conn, user_id, 1)
        user = db.user_by_id(conn, user_id)
    _load_demo_sample(conn, user, through)
    return int(user["id"])


def _load_demo_sample(conn, user: dict, through: date) -> None:
    """Migrate the old sample once, then append new sessions under the seed lock."""
    user_id = user["id"]
    records = sample_trades(through)
    existing = db.sample_count(conn, user_id, DEMO_NOTE)
    unplanned = _demo_trades_without_plan(conn, user_id)
    accounts = db.accounts(conn, user_id)
    legacy = next((row for row in accounts if row["name"] in FORMER_DEMO_PROP_NAMES), None)
    has_funded = any(row["name"] == DEMO_FUNDED_NAME for row in accounts)
    if existing >= len(records) and legacy is None and has_funded and not unplanned:
        return
    if not existing:
        for trade in db.trades(conn, user["id"]):
            note = trade["notes"] or ""
            if note == SAMPLE_NOTE or note.startswith(("Omensite demo v2 ", "Omensite demo v3 ")):
                db.delete_trade(conn, user["id"], trade["id"])
    personal_id = next(row["id"] for row in accounts if row["kind"] == "personal")
    prop_id = next((row["id"] for row in accounts if row["name"] == DEMO_PROP["name"]), None)
    if legacy is not None and prop_id is None:
        prop_id = legacy["id"]
        conn.execute(
            "UPDATE accounts SET name = ?, profit_target = ? WHERE user_id = ? AND id = ?",
            (DEMO_PROP["name"], DEMO_PROP["profit_target"], user_id, prop_id),
        )
    if prop_id is None:
        prop_id = db.insert_account(
            conn, user["id"], DEMO_PROP["name"], DEMO_PROP["kind"], DEMO_PROP["starting_balance"],
            DEMO_PROP["daily_loss_limit"], DEMO_PROP["trailing_drawdown"], DEMO_PROP["profit_target"],
        )
    if legacy is not None or not existing:
        db.set_consistency(conn, user_id, prop_id, DEMO_PROP["consistency_pct"])
    if not has_funded:
        db.insert_account(conn, user_id, DEMO_FUNDED_NAME, "prop", 0, None, None, None)
    if legacy is not None and legacy["name"] == LEGACY_DEMO_PROP:
        # Reclassify the sample fills in place so their IDs and P&L stay stable.
        conn.execute(
            """UPDATE trades
               SET account_id = CASE WHEN closed_local >= ? AND closed_local < ? THEN ? ELSE ? END
               WHERE user_id = ? AND notes = ?""",
            (CHALLENGE_START.isoformat(), (CHALLENGE_END + timedelta(days=1)).isoformat(),
             prop_id, personal_id, user_id, DEMO_NOTE),
        )
    for trade in unplanned:
        plan = demo_trade_plan(
            trade["instrument"], trade["direction"], trade["avg_entry"], trade["qty_entered"],
            parse_iso(trade["opened_at"]).astimezone(NY), trade["net_pnl"],
        )
        db.update_trade(conn, user_id, trade["id"], plan)
    checks = [{"item_id": item["id"], "checked": 1} for item in db.checklist(conn, user["id"]) if item["active"]]
    for record in records[existing:]:
        moment = datetime.fromisoformat(record["opened_at"]).replace(tzinfo=NY)
        closed = datetime.fromisoformat(record["closed_at"]).replace(tzinfo=NY)
        legs = [Leg("entry", record["qty"], record["entry"], moment),
                Leg("exit", record["qty"], record["exit"], closed)]
        fields, leg_rows = compose(
            zone=user_zone(user), instrument=record["instrument"], asset_class="future",
            direction=record["direction"], fees=record["fees"], legs=legs,
            stop=record["stop"], target=record["target"],
            account_id=prop_id if record["is_prop"] else personal_id,
            session=record["session"], kill_zone=record["kill_zone"],
            setup=record["setup"], grade=record["grade"], notes=DEMO_NOTE,
            emotion_before=record["emotion_before"], emotion_after="Reflective",
            followed_plan=record["followed_plan"],
            lesson="Wait for confirmation at the level. Review execution after the session.",
        )
        save_trade(conn, user["id"], {"trade": fields, "legs": leg_rows,
                   "tags": ["FVG"] if record["setup"] == "Fair value gap" else [],
                   "mistakes": [], "checks": checks})


def finish_onboarding(conn, user: dict, form) -> None:
    from app.firms import FIRMS

    chosen = []
    for market in _values(form, "markets"):
        if market in {"ES", "NQ", "MES", "MNQ", "stocks"} and market not in chosen:
            chosen.append(market)
    db.set_markets(conn, user["id"], ",".join(chosen))
    for key, preset in FIRMS.items():
        if key not in _values(form, "firms"):
            continue
        kind_raw = _one(form, f"{key}_kind") or "eval"
        kind = {"eval": "prop", "funded": "prop", "personal": "personal"}.get(kind_raw, "prop")
        name = preset["name"] if kind_raw != "funded" else preset["name"].replace("Eval", "Funded")
        if kind_raw == "personal":
            name = preset["name"].replace("Eval", "Personal")
        daily = _optional_number(form, f"{key}_daily", preset["daily"])
        trail = _optional_number(form, f"{key}_trail", preset["trail"])
        target = _optional_number(form, f"{key}_target", preset["target"])
        consistency = _optional_number(form, f"{key}_consistency", preset["consistency"])
        try:
            account_id = db.insert_account(
                conn, user["id"], name, kind, preset["starting"], daily, trail, target
            )
        except sqlite3.IntegrityError:
            continue
        db.set_consistency(conn, user["id"], account_id, consistency)
    seen = set()
    for setup in _values(form, "setups"):
        if setup not in TAGS or setup in seen:
            continue
        seen.add(setup)
        db.insert_playbook(
            conn,
            user["id"],
            setup,
            f"Favorite setup: {setup}.",
            "Write the rules you actually take.",
            "",
            utc_iso(datetime.now(UTC)),
        )
    db.set_onboarded(conn, user["id"], 1)


def _optional_number(form, key: str, fallback):
    raw = _one(form, key).strip()
    if raw == "":
        return fallback
    try:
        number = float(raw)
    except ValueError as exc:
        raise JournalError("Use numbers for the account rules.") from exc
    if not math.isfinite(number) or number < 0:
        raise JournalError("Use numbers for the account rules.")
    return number


def dashboard_context(conn, user: dict, account_id: int | None = None, range_key: str = "all", month_key: str = "") -> dict:
    zone = user_zone(user)
    all_trades = db.trades(conn, user["id"])
    raw = all_trades
    if account_id is not None:
        raw = [trade for trade in raw if trade["account_id"] == account_id]
    today = datetime.now(zone).date()
    since = None
    if range_key == "7d":
        since = today - timedelta(days=6)
    elif range_key == "30d":
        since = today - timedelta(days=29)
    elif range_key == "mtd":
        since = today.replace(day=1)
    if since is not None:
        stamp = since.isoformat()
        raw = [
            trade
            for trade in raw
            if (trade.get("closed_local") or trade.get("closed_at")
                or trade.get("opened_local") or trade.get("opened_at") or "")[:10] >= stamp
        ]
    tags = db.tags_for_user(conn, user["id"])
    mistakes = db.mistakes_for_user(conn, user["id"])
    events = db.news_events(conn)
    math = _math_rows(raw, mistakes)
    board = dashboard(math, tags)
    latest = max((trade["closed_at"][:10] for trade in math if trade["is_closed"] and trade["closed_at"]), default=today.isoformat())
    try:
        selected_month = date.fromisoformat(month_key + "-01") if month_key else date.fromisoformat(latest)
    except ValueError:
        selected_month = date.fromisoformat(latest)
    sections = []
    for title, key in _BREAKDOWNS:
        rows = board[key]
        if key == "by_setup" and rows and all(row["name"] == "Unset" for row in rows):
            continue
        sections.append({"title": title, "rows": rows})
    window = int(user["news_window_minutes"])
    recent = []
    for trade in raw[:8]:
        item = dict(trade)
        item["when"] = show_time(item.get("opened_at"), zone)
        item["news"] = news_near(item.get("opened_at"), events, window)
        item["tags"] = tags.get(item["id"], [])
        item["mistakes"] = mistakes.get(item["id"], [])
        recent.append(item)
    accounts = db.accounts(conn, user["id"])
    if user["email"] == DEMO_EMAIL:
        prop_accounts = [account for account in accounts if account_id in (None, account["id"])]
        props = prop_rows(prop_accounts, _math_rows(all_trades, {}), today)
        for row in props:
            if row["account"]["name"] == DEMO_PROP["name"]:
                row["challenge"] = demo_challenge(row)
            elif row["account"]["name"] == DEMO_FUNDED_NAME:
                row["funded_placeholder"] = True
    else:
        props = prop_rows(accounts, math, today)
    return {
        "dash": board,
        "calendar": month_calendar(math, selected_month),
        "sections": sections,
        "props": props,
        "recent": recent,
        "equity_svg": equity_svg(board["equity"]),
        "zone_name": str(zone),
        "accounts": accounts,
        "range_key": range_key if range_key in {"7d", "30d", "mtd", "all"} else "all",
        "account_filter": "" if account_id is None else str(account_id),
    }


def trade_detail(conn, user: dict, trade_id: int) -> dict | None:
    row = db.trade(conn, user["id"], trade_id)
    if row is None:
        return None
    zone = user_zone(user)
    events = db.news_events(conn)
    legs = []
    for leg in db.legs(conn, trade_id):
        item = dict(leg)
        item["when"] = show_time(leg["filled_at"], zone)
        legs.append(item)
    by_slot = {shot["slot"]: shot for shot in db.shots(conn, trade_id)}
    warnings = []
    if row["direction"] == "long" and row["stop"] and row["avg_entry"] and row["stop"] >= row["avg_entry"]:
        warnings.append("The stop is not below the average entry.")
    if row["direction"] == "short" and row["stop"] and row["avg_entry"] and row["stop"] <= row["avg_entry"]:
        warnings.append("The stop is not above the average entry.")
    return {
        "trade": row,
        "legs": legs,
        "checks": db.checks_for_trade(conn, trade_id),
        "tags": db.tags_for_user(conn, user["id"]).get(trade_id, []),
        "mistakes": db.mistakes_for_user(conn, user["id"]).get(trade_id, []),
        "slots": [{"key": key, "label": label, "shot": by_slot.get(key)} for key, label in SHOT_SLOTS],
        "news": news_near(row.get("opened_at"), events, int(user["news_window_minutes"])),
        "embed": chart_embed(row),
        "warnings": warnings,
        "when": show_time(row.get("opened_at"), zone),
        "closed_label": show_time(row.get("closed_at"), zone),
    }


def chart_embed(trade: dict) -> dict | None:
    from urllib.parse import quote

    try:
        spec = spec_for(trade["asset_class"], trade["instrument"])
    except ValueError:
        return None
    symbol = quote(spec.tv_symbol, safe="")
    return {
        "symbol": spec.tv_symbol,
        "embed": f"https://s.tradingview.com/widgetembed/?symbol={symbol}&interval=5&theme=dark&style=1&locale=en",
        "link": f"https://www.tradingview.com/chart/?symbol={symbol}",
    }


def news_context(conn, user: dict) -> dict:
    zone = user_zone(user)
    today = datetime.now(zone).date()
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)
    events = db.news_events(conn)
    days = []
    for offset in range(7):
        day = week_start + timedelta(days=offset)
        days.append({"date": day.isoformat(), "label": day.strftime("%A, %b %d"), "events": []})
    by_date = {row["date"]: row for row in days}
    recent, later, holidays, early = [], [], [], []
    recent_start = week_start - timedelta(days=14)
    later_end = week_end + timedelta(days=40)
    rank = {"high": 0, "medium": 1, "low": 2}
    for event in events:
        moment = parse_iso(event["when_utc"])
        local = moment.astimezone(zone)
        ny = moment.astimezone(NY)
        view = {
            "title": event["title"],
            "impact": event["impact"],
            "time": local.strftime("%I:%M %p").lstrip("0"),
            "sort": local.strftime("%H:%M"),
            "actual": event["actual"] or "",
            "forecast": event["forecast"] or "",
            "previous": event["previous"] or "",
            "note": event["note"] or "",
            "ny_date": ny.strftime("%a %b %d"),
        }
        if event["category"] == "holiday":
            holidays.append(view)
            continue
        if event["category"] == "early_close":
            early.append(view)
            continue
        local_day = local.date()
        if week_start <= local_day <= week_end:
            by_date[local_day.isoformat()]["events"].append(view)
        elif recent_start <= local_day < week_start and event["impact"] == "high":
            recent.append(view)
        elif week_end < local_day <= later_end and event["impact"] == "high":
            later.append(view)
    for row in days:
        row["events"].sort(key=lambda item: (rank.get(item["impact"], 9), item["sort"]))
    flagged = 0
    window = int(user["news_window_minutes"])
    for trade in db.trades(conn, user["id"]):
        if news_near(trade.get("opened_at"), events, window):
            flagged += 1
    earnings = []
    for row in db.earning_rows(conn, user["id"]):
        item = dict(row)
        item["when"] = show_time(row["when_at"], zone)
        earnings.append(item)
    snapshot = []
    for event in events:
        if event["category"] != "economic":
            continue
        moment = parse_iso(event["when_utc"]).astimezone(zone)
        snapshot.append(
            {
                "title": event["title"],
                "impact": event["impact"],
                "when": moment.strftime("%b %d, %Y %H:%M"),
                "actual": event["actual"] or "",
                "forecast": event["forecast"] or "",
                "previous": event["previous"] or "",
                "note": event["note"] or "",
            }
        )
    return {
        "week_label": f"{week_start.strftime('%b %d')} - {week_end.strftime('%b %d, %Y')}",
        "days": days,
        "recent": recent,
        "later": later,
        "holidays": holidays,
        "early": early,
        "watchlist": db.watch_rows(conn, user["id"]),
        "earnings": earnings,
        "window": window,
        "caveat": CAVEAT,
        "flagged": flagged,
        "snapshot": snapshot,
    }


def plan_context(conn, user: dict, day_text: str) -> dict:
    zone = user_zone(user)
    if day_text:
        try:
            day = date.fromisoformat(day_text)
        except ValueError as exc:
            raise JournalError("That date is not valid.") from exc
    else:
        day = datetime.now(zone).date()
    row = db.day_row(conn, user["id"], day.isoformat()) or {
        "bias": "",
        "key_levels": "",
        "draw": "",
        "news_to_watch": "",
        "eod_review": "",
    }
    opened = []
    for trade in decorate_trades(conn, user):
        if (trade.get("opened_local") or "").startswith(day.isoformat()):
            opened.append(trade)
    return {"day": day.isoformat(), "plan": row, "opened": opened}


def save_plan(conn, user: dict, form) -> str:
    day = _one(form, "day").strip()
    try:
        date.fromisoformat(day)
    except ValueError as exc:
        raise JournalError("That date is not valid.") from exc
    db.save_day(
        conn,
        user["id"],
        day,
        _choice(_one(form, "bias"), BIASES, "Bias"),
        _clip(_one(form, "key_levels"), "Key levels", 4000),
        _choice(_one(form, "draw"), DRAWS, "Draw on liquidity"),
        _clip(_one(form, "news_to_watch"), "News to watch", 4000),
        _clip(_one(form, "eod_review"), "End-of-day review", 4000),
    )
    return day


def review_context(conn, user: dict, week_text: str, month_text: str) -> dict:
    zone = user_zone(user)
    today = datetime.now(zone).date()
    try:
        anchor = date.fromisoformat(week_text) if week_text else today
    except ValueError as exc:
        raise JournalError("That week is not valid.") from exc
    week_start = anchor - timedelta(days=anchor.weekday())
    week_end = week_start + timedelta(days=6)
    if month_text:
        try:
            year, month = (int(part) for part in month_text.split("-"))
            month_start = date(year, month, 1)
        except ValueError as exc:
            raise JournalError("That month is not valid.") from exc
    else:
        month_start = today.replace(day=1)
    if month_start.month == 12:
        month_end = date(month_start.year + 1, 1, 1) - timedelta(days=1)
    else:
        month_end = date(month_start.year, month_start.month + 1, 1) - timedelta(days=1)
    raw = db.trades(conn, user["id"])
    tags = db.tags_for_user(conn, user["id"])
    mistakes = db.mistakes_for_user(conn, user["id"])
    math = _math_rows(raw, mistakes)
    return {
        "week_start": week_start.isoformat(),
        "week_end": week_end.isoformat(),
        "month_value": month_start.strftime("%Y-%m"),
        "month_label": month_start.strftime("%B %Y"),
        "week": review_slice(math, tags, week_start, week_end),
        "month": review_slice(math, tags, month_start, month_end),
    }


def sniff_image(data: bytes) -> str:
    if len(data) > 8 * 1024 * 1024:
        raise JournalError("Images are limited to 8 MB.")
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if data.startswith(b"\xff\xd8"):
        return ".jpg"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return ".gif"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return ".webp"
    raise JournalError("Use a PNG, JPEG, GIF, or WebP image.")


def store_image(conn, user_id: int, data: bytes) -> str:
    name = f"{uuid4().hex}{sniff_image(data)}"
    db.store_media(conn, user_id, name, data)
    return name


def read_image(conn, user_id: int, filename: str) -> bytes | None:
    path = upload_path(user_id, filename)
    content = db.media_content(conn, user_id, filename)
    if content is not None:
        return content
    # Existing local journals can still read their previously uploaded files.
    return path.read_bytes() if path.is_file() else None


def delete_image(conn, user_id: int, filename: str) -> None:
    db.delete_media(conn, user_id, filename)
    upload_path(user_id, filename).unlink(missing_ok=True)


def clean_markup(shapes) -> str:
    if not isinstance(shapes, list):
        raise JournalError("Markup has to be a list of shapes.")
    if len(shapes) > 200:
        raise JournalError("Markup is limited to 200 shapes.")
    clean = []
    for shape in shapes:
        if not isinstance(shape, dict) or shape.get("type") not in {"arrow", "box", "line", "text"}:
            raise JournalError("A markup shape is incomplete.")
        color = str(shape.get("color") or "").lower()
        if color not in _COLORS:
            raise JournalError("That markup color is not in the palette.")
        point = {"type": shape["type"], "color": color}
        for key in ("x1", "y1", "x2", "y2"):
            try:
                value = float(shape.get(key))
            except (TypeError, ValueError) as exc:
                raise JournalError("Markup points have to be numbers.") from exc
            if not math.isfinite(value) or value < 0 or value > 1:
                raise JournalError("Markup points have to sit on the image.")
            point[key] = round(value, 4)
        point["text"] = str(shape.get("text") or "")[:200]
        clean.append(point)
    return json.dumps(clean)


def save_trade_shot(conn, user: dict, trade_id: int, slot: str, data: bytes) -> int:
    if slot not in {key for key, _label in SHOT_SLOTS}:
        raise JournalError("Choose a chart slot.")
    if db.trade(conn, user["id"], trade_id) is None:
        raise JournalError("Trade not found.")
    existing = next((shot for shot in db.shots(conn, trade_id) if shot["slot"] == slot), None)
    filename = store_image(conn, user["id"], data)
    shot_id = db.upsert_shot(conn, user["id"], trade_id, slot, filename, utc_iso(datetime.now(UTC)))
    if existing and existing["filename"] != filename:
        delete_image(conn, user["id"], existing["filename"])
    return shot_id


def save_shot_markup(conn, user: dict, shot_id: int, shapes) -> None:
    if not db.set_markup(conn, user["id"], shot_id, clean_markup(shapes)):
        raise JournalError("Chart not found.")


def remove_shot(conn, user: dict, shot_id: int) -> None:
    row = db.delete_shot(conn, user["id"], shot_id)
    if row is None:
        raise JournalError("Chart not found.")
    delete_image(conn, user["id"], row["filename"])


def _preview_path(user_id: int, token: str):
    if not token or not _TOKEN.fullmatch(token):
        return None
    return import_dir(user_id) / f"{token}.json"


def build_preview(user_id: int, text: str, zone: ZoneInfo) -> tuple[str, list[dict]]:
    try:
        parsed = parse_csv(text, zone)
    except CsvImportError as exc:
        raise JournalError(str(exc)) from exc
    folder = import_dir(user_id)
    cutoff = time.time() - 86400
    for path in folder.glob("*.json"):
        if path.stat().st_mtime < cutoff:
            path.unlink(missing_ok=True)
    token = new_token()
    serial = []
    rows = []
    for item in parsed:
        copy = {
            "instrument": item["instrument"],
            "asset_class": item["asset_class"],
            "direction": item["direction"],
            "fees": item["fees"],
            "warnings": item["warnings"],
            "legs": [
                {
                    "kind": leg["kind"],
                    "qty": leg["qty"],
                    "price": leg["price"],
                    "filled_at": leg["filled_at"].isoformat(),
                }
                for leg in item["legs"]
            ],
        }
        serial.append(copy)
        rows.append(
            {
                "instrument": item["instrument"],
                "direction": item["direction"],
                "asset_class": item["asset_class"],
                "legs": len(item["legs"]),
                "fees": item["fees"],
                "when": show_time(utc_iso(item["legs"][0]["filled_at"]), zone),
                "warnings": item["warnings"],
            }
        )
    (folder / f"{token}.json").write_text(json.dumps(serial), encoding="utf-8")
    return token, rows


def load_preview(user_id: int, token: str) -> list[dict]:
    path = _preview_path(user_id, token)
    if path is None or not path.is_file():
        raise JournalError("That import expired. Upload the file again.")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise JournalError("That import could not be read. Upload the file again.") from exc
    for item in data:
        for leg in item["legs"]:
            leg["filled_at"] = parse_iso(leg["filled_at"])
    return data


def parsed_from_import(item: dict, account_id: int, zone: ZoneInfo) -> dict:
    legs = [Leg(leg["kind"], float(leg["qty"]), float(leg["price"]), leg["filled_at"]) for leg in item["legs"]]
    fields, leg_rows = compose(
        zone=zone,
        instrument=item["instrument"],
        asset_class=item["asset_class"],
        direction=item["direction"],
        fees=float(item.get("fees") or 0),
        legs=legs,
        account_id=account_id,
        notes=" ".join(item.get("warnings") or []),
    )
    return {"trade": fields, "legs": leg_rows, "tags": [], "mistakes": [], "checks": []}


def confirm_import(conn, user: dict, token: str, account_id: int) -> int:
    if db.account(conn, user["id"], account_id) is None:
        raise JournalError("Choose an account.")
    items = load_preview(user["id"], token)
    zone = user_zone(user)
    for item in items:
        save_trade(conn, user["id"], parsed_from_import(item, account_id, zone))
    return len(items)


def discard_preview(user_id: int, token: str) -> None:
    path = _preview_path(user_id, token)
    if path is not None and path.is_file():
        path.unlink()


def export_csv_text(conn, user: dict) -> str:
    tags = db.tags_for_user(conn, user["id"])
    mistakes = db.mistakes_for_user(conn, user["id"])
    events = db.news_events(conn)
    window = int(user["news_window_minutes"])
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "id", "instrument", "asset_class", "direction", "account", "qty", "avg_entry", "avg_exit",
            "opened_utc", "closed_utc", "net_pnl", "points", "ticks", "r_multiple", "planned_r",
            "session", "kill_zone", "macro", "grade", "followed_plan", "setup", "tags", "mistakes",
            "emotion_before", "emotion_after", "news_flag", "lesson",
        ]
    )
    for trade in db.trades(conn, user["id"]):
        writer.writerow(
            [
                trade["id"], trade["instrument"], trade["asset_class"], trade["direction"], trade["account_name"],
                trade["qty_entered"], trade["avg_entry"], trade["avg_exit"], trade["opened_at"], trade["closed_at"],
                trade["net_pnl"], trade["points"], trade["ticks"], trade["r_multiple"], trade["planned_r"],
                trade["session"], trade["kill_zone"], trade["macro_window"], trade["grade"],
                "" if trade["followed_plan"] is None else "yes" if trade["followed_plan"] else "no",
                trade["setup"], "; ".join(tags.get(trade["id"], [])), "; ".join(mistakes.get(trade["id"], [])),
                trade["emotion_before"], trade["emotion_after"],
                "yes" if news_near(trade.get("opened_at"), events, window) else "no",
                trade["lesson"],
            ]
        )
    return buffer.getvalue()


def export_backup(conn, user: dict) -> dict:
    user_id = user["id"]
    tags = db.tags_for_user(conn, user_id)
    mistakes = db.mistakes_for_user(conn, user_id)
    trade_rows = []
    for trade in db.trades(conn, user_id):
        item = {key: trade[key] for key in db.TRADE_FIELDS if key in trade and key != "user_id"}
        item["account_name"] = trade["account_name"]
        item["legs"] = [
            {"kind": leg["kind"], "qty": leg["qty"], "price": leg["price"], "filled_at": leg["filled_at"]}
            for leg in db.legs(conn, trade["id"])
        ]
        item["tags"] = tags.get(trade["id"], [])
        item["mistakes"] = mistakes.get(trade["id"], [])
        item["checks"] = [
            {"label": row["label"], "checked": row["checked"]}
            for row in db.checks_for_trade(conn, trade["id"])
        ]
        shots = []
        for shot in db.shots(conn, trade["id"]):
            content = read_image(conn, user_id, shot["filename"])
            if content is None:
                continue
            shots.append(
                {
                    "slot": shot["slot"],
                    "markup_json": shot["markup_json"],
                    "data_b64": base64.b64encode(content).decode("ascii"),
                }
            )
        item["screenshots"] = shots
        trade_rows.append(item)
    books = []
    for book in db.playbooks(conn, user_id):
        images = []
        for image in db.playbook_images(conn, book["id"]):
            content = read_image(conn, user_id, image["filename"])
            if content is not None:
                images.append({"data_b64": base64.b64encode(content).decode("ascii")})
        books.append(
            {
                "name": book["name"],
                "setup": book["setup"] or "",
                "rules": book["rules"] or "",
                "example_notes": book["example_notes"] or "",
                "images": images,
            }
        )
    return {
        "version": 1,
        "exported_at": utc_iso(datetime.now(UTC)),
        "timezone": user["timezone"],
        "news_window_minutes": user["news_window_minutes"],
        "accounts": [
            {
                "name": row["name"],
                "kind": row["kind"],
                "starting_balance": row["starting_balance"],
                "daily_loss_limit": row["daily_loss_limit"],
                "trailing_drawdown": row["trailing_drawdown"],
                "profit_target": row["profit_target"],
            }
            for row in db.accounts(conn, user_id)
        ],
        "checklist": [
            {"label": row["label"], "position": row["position"], "active": row["active"]}
            for row in db.checklist(conn, user_id)
        ],
        "trades": trade_rows,
        "days": db.many(
            conn,
            "SELECT day, bias, key_levels, draw, news_to_watch, eod_review FROM days WHERE user_id = ? ORDER BY day",
            (user_id,),
        ),
        "playbooks": books,
        "watchlist": [row["symbol"] for row in db.watch_rows(conn, user_id)],
        "earnings": [
            {"symbol": row["symbol"], "when_at": row["when_at"], "note": row["note"] or ""}
            for row in db.earning_rows(conn, user_id)
        ],
    }


def _optional_float(value) -> float | None:
    if value is None or value == "":
        return None
    return float(value)


def restore_backup(conn, user: dict, payload: dict) -> int:
    if not isinstance(payload, dict) or payload.get("version") != 1:
        raise JournalError("This backup is not version 1 of an Omensite Journal file.")
    user_id = user["id"]
    zone_name = payload.get("timezone")
    window = payload.get("news_window_minutes")
    if isinstance(zone_name, str) and isinstance(window, int) and 1 <= window <= 180:
        try:
            ZoneInfo(zone_name)
        except ZoneInfoNotFoundError:
            pass
        else:
            db.update_user(conn, user_id, zone_name, window)
    account_ids = {}
    for row in db.accounts(conn, user_id):
        account_ids[row["name"]] = row["id"]
    for row in payload.get("accounts") or []:
        if not isinstance(row, dict):
            continue
        name = str(row.get("name") or "").strip()[:80]
        kind = row.get("kind")
        if not name or kind not in ACCOUNT_KINDS or name in account_ids:
            continue
        try:
            account_ids[name] = db.insert_account(
                conn,
                user_id,
                name,
                kind,
                float(row.get("starting_balance") or 0),
                _optional_float(row.get("daily_loss_limit")),
                _optional_float(row.get("trailing_drawdown")),
                _optional_float(row.get("profit_target")),
            )
        except (TypeError, ValueError) as exc:
            raise JournalError("An account in the backup has a balance that is not a number.") from exc
    for row in payload.get("checklist") or []:
        if not isinstance(row, dict):
            continue
        label = str(row.get("label") or "").strip()[:200]
        if not label:
            continue
        have = {item["label"] for item in db.checklist(conn, user_id)}
        if label in have:
            continue
        item_id = db.add_check(conn, user_id, label, len(have))
        if not row.get("active", 1):
            db.disable_check(conn, user_id, item_id)
    label_ids = {item["label"]: item["id"] for item in db.checklist(conn, user_id)}
    if not account_ids:
        raise JournalError("The backup has no account to attach trades to.")
    fallback = next(iter(account_ids.values()))
    zone = user_zone(user)
    if isinstance(zone_name, str):
        try:
            zone = ZoneInfo(zone_name)
        except ZoneInfoNotFoundError:
            pass
    created: list[str] = []
    restored = 0
    try:
        for trade in payload.get("trades") or []:
            if not isinstance(trade, dict):
                continue
            name = str(trade.get("account_name") or "").strip()
            account_id = account_ids.get(name, fallback)
            legs = []
            for leg in trade.get("legs") or []:
                legs.append(Leg(leg["kind"], float(leg["qty"]), float(leg["price"]), parse_iso(leg["filled_at"])))
            check_rows = []
            checked = 0
            for item in trade.get("checks") or []:
                item_id = label_ids.get(str(item.get("label") or ""))
                if not item_id:
                    continue
                flag = 1 if item.get("checked") else 0
                checked += flag
                check_rows.append({"item_id": item_id, "checked": flag})
            auto = grade_for(checked, len(check_rows))
            picked = trade.get("grade") if trade.get("grade_manual") else None
            if picked not in GRADES:
                picked = None
            fields, leg_rows = compose(
                zone=zone,
                instrument=str(trade.get("instrument") or ""),
                asset_class=str(trade.get("asset_class") or ""),
                direction=str(trade.get("direction") or ""),
                fees=float(trade.get("fees") or 0),
                legs=legs,
                account_id=account_id,
                stop=_optional_float(trade.get("stop")),
                target=_optional_float(trade.get("target")),
                mae=_optional_float(trade.get("mae_price")),
                mfe=_optional_float(trade.get("mfe_price")),
                session=trade.get("session") if trade.get("session") in SESSIONS else None,
                kill_zone=trade.get("kill_zone") if trade.get("kill_zone") in KILL_ZONES else None,
                macro_window=trade.get("macro_window") if trade.get("macro_window") in MACROS else None,
                htf_bias=trade.get("htf_bias") if trade.get("htf_bias") in BIASES else "",
                draw=trade.get("draw") if trade.get("draw") in DRAWS else "",
                premium=trade.get("premium") if trade.get("premium") in PREMIUM else "",
                range_high=_optional_float(trade.get("range_high")),
                range_low=_optional_float(trade.get("range_low")),
                setup=str(trade.get("setup") or "")[:80],
                grade=picked or auto,
                auto_grade=auto,
                grade_manual=1 if picked else 0,
                went_right=str(trade.get("went_right") or "")[:4000],
                went_wrong=str(trade.get("went_wrong") or "")[:4000],
                lesson=str(trade.get("lesson") or "")[:4000],
                notes=str(trade.get("notes") or "")[:4000],
                emotion_before=trade.get("emotion_before") if trade.get("emotion_before") in EMOTIONS else "",
                emotion_after=trade.get("emotion_after") if trade.get("emotion_after") in EMOTIONS else "",
                confidence=trade.get("confidence") if isinstance(trade.get("confidence"), int) and 1 <= trade["confidence"] <= 10 else None,
                followed_plan=trade.get("followed_plan") if trade.get("followed_plan") in (0, 1) else None,
            )
            trade_id = save_trade(
                conn,
                user_id,
                {
                    "trade": fields,
                    "legs": leg_rows,
                    "tags": [tag for tag in trade.get("tags") or [] if tag in TAGS],
                    "mistakes": [tag for tag in trade.get("mistakes") or [] if tag in MISTAKES],
                    "checks": check_rows,
                },
            )
            for shot in trade.get("screenshots") or []:
                data = base64.b64decode(shot.get("data_b64") or "", validate=True)
                filename = store_image(conn, user_id, data)
                created.append(filename)
                if shot.get("slot") not in {"htf", "entry", "after_exit"}:
                    delete_image(conn, user_id, filename)
                    created.pop()
                    continue
                shot_id = db.upsert_shot(conn, user_id, trade_id, shot.get("slot"), filename, utc_iso(datetime.now(UTC)))
                markup = shot.get("markup_json") or "[]"
                try:
                    db.set_markup(conn, user_id, shot_id, clean_markup(json.loads(markup)))
                except (JournalError, json.JSONDecodeError):
                    db.set_markup(conn, user_id, shot_id, "[]")
            restored += 1
        have_days = {row["day"] for row in db.many(conn, "SELECT day FROM days WHERE user_id = ?", (user_id,))}
        for day in payload.get("days") or []:
            stamp = str(day.get("day") or "")
            if stamp in have_days or len(stamp) != 10:
                continue
            db.save_day(
                conn,
                user_id,
                stamp,
                day.get("bias") if day.get("bias") in BIASES else "",
                str(day.get("key_levels") or "")[:4000],
                day.get("draw") if day.get("draw") in DRAWS else "",
                str(day.get("news_to_watch") or "")[:4000],
                str(day.get("eod_review") or "")[:4000],
            )
        for book in payload.get("playbooks") or []:
            book_id = db.insert_playbook(
                conn,
                user_id,
                str(book.get("name") or "Setup")[:120],
                str(book.get("setup") or "")[:8000],
                str(book.get("rules") or "")[:8000],
                str(book.get("example_notes") or "")[:8000],
                utc_iso(datetime.now(UTC)),
            )
            for image in book.get("images") or []:
                data = base64.b64decode(image.get("data_b64") or "", validate=True)
                filename = store_image(conn, user_id, data)
                created.append(filename)
                db.add_playbook_image(conn, user_id, book_id, filename, utc_iso(datetime.now(UTC)))
        for symbol in payload.get("watchlist") or []:
            try:
                root = future_root(parse_symbol(str(symbol)))
                db.add_watch(conn, user_id, root or parse_symbol(str(symbol)))
            except ValueError:
                continue
        for row in payload.get("earnings") or []:
            try:
                symbol = future_root(parse_symbol(str(row.get("symbol") or ""))) or parse_symbol(str(row.get("symbol") or ""))
                when = utc_iso(parse_iso(str(row.get("when_at") or "")))
            except (ValueError, TypeError):
                continue
            db.add_earning(conn, user_id, symbol, when, str(row.get("note") or "")[:400])
    except Exception:
        for name in created:
            delete_image(conn, user_id, name)
        raise
    return restored


def create_account_for(conn, user: dict, form) -> None:
    name = _clip(_one(form, "name"), "Account name", 80)
    if not name:
        raise JournalError("Name the account.")
    kind = _one(form, "kind").strip()
    if kind not in ACCOUNT_KINDS:
        raise JournalError("Account type is personal, prop, or sim.")
    try:
        db.insert_account(
            conn,
            user["id"],
            name,
            kind,
            _number(_one(form, "starting_balance"), "Starting balance", allow_zero=True) or 0,
            _number(_one(form, "daily_loss_limit"), "Daily loss limit"),
            _number(_one(form, "trailing_drawdown"), "Trailing drawdown"),
            _number(_one(form, "profit_target"), "Profit target"),
        )
    except sqlite3.IntegrityError as exc:
        raise JournalError("You already have an account with that name.") from exc


def remove_account_for(conn, user: dict, account_id: int) -> None:
    row = db.account(conn, user["id"], account_id)
    if row is None:
        raise JournalError("Account not found.")
    if any(trade["account_id"] == account_id for trade in db.trades(conn, user["id"])):
        raise JournalError("This account still has trades. Move or delete those trades first.")
    db.delete_account(conn, user["id"], account_id)


def add_checklist_item(conn, user: dict, label: str) -> None:
    text = _clip(label, "Checklist item", 200)
    if not text:
        raise JournalError("Write the checklist item.")
    position = len(db.checklist(conn, user["id"]))
    db.add_check(conn, user["id"], text, position)


def disable_checklist_item(conn, user: dict, item_id: int) -> None:
    db.disable_check(conn, user["id"], item_id)


def save_playbook(conn, user: dict, form, playbook_id: int | None = None) -> int:
    name = _clip(_one(form, "name"), "Name", 120)
    if not name:
        raise JournalError("Name the setup.")
    setup = _clip(_one(form, "setup"), "Setup", 8000)
    rules = _clip(_one(form, "rules"), "Rules", 8000)
    notes = _clip(_one(form, "example_notes"), "Notes", 8000)
    if playbook_id is None:
        return db.insert_playbook(conn, user["id"], name, setup, rules, notes, utc_iso(datetime.now(UTC)))
    if not db.update_playbook(conn, user["id"], playbook_id, name, setup, rules, notes):
        raise JournalError("Setup not found.")
    return playbook_id


def remove_playbook(conn, user: dict, playbook_id: int) -> None:
    if db.playbook(conn, user["id"], playbook_id) is None:
        raise JournalError("Setup not found.")
    names = [image["filename"] for image in db.playbook_images(conn, playbook_id)]
    db.delete_playbook(conn, user["id"], playbook_id)
    for name in names:
        delete_image(conn, user["id"], name)


def add_playbook_shot(conn, user: dict, playbook_id: int, data: bytes) -> None:
    if db.playbook(conn, user["id"], playbook_id) is None:
        raise JournalError("Setup not found.")
    filename = store_image(conn, user["id"], data)
    db.add_playbook_image(conn, user["id"], playbook_id, filename, utc_iso(datetime.now(UTC)))


def remove_playbook_shot(conn, user: dict, image_id: int) -> None:
    row = db.delete_playbook_image(conn, user["id"], image_id)
    if row is None:
        raise JournalError("Image not found.")
    delete_image(conn, user["id"], row["filename"])


def add_symbol_watch(conn, user: dict, raw: str) -> None:
    try:
        symbol = parse_symbol(raw)
    except ValueError as exc:
        raise JournalError(str(exc)) from exc
    db.add_watch(conn, user["id"], future_root(symbol) or symbol)


def add_earnings_row(conn, user: dict, form, zone: ZoneInfo) -> None:
    try:
        symbol = parse_symbol(_one(form, "symbol"))
    except ValueError as exc:
        raise JournalError(str(exc)) from exc
    symbol = future_root(symbol) or symbol
    when = _parse_clock(_one(form, "when"), zone)
    note = _clip(_one(form, "note"), "Note", 400)
    db.add_watch(conn, user["id"], symbol)
    db.add_earning(conn, user["id"], symbol, utc_iso(when), note)


def load_sample(conn, user: dict) -> str:
    if db.sample_count(conn, user["id"], SAMPLE_NOTE) > 0:
        return "sample-exists"
    zone = user_zone(user)
    today = datetime.now(NY).date()
    past = []
    cursor = today - timedelta(days=1)
    while len(past) < 10:
        if cursor.weekday() < 5:
            past.append(cursor)
        cursor -= timedelta(days=1)
    past.reverse()
    personal = next((row for row in db.accounts(conn, user["id"]) if row["kind"] == "personal"), None)
    if personal is None:
        personal_id = db.insert_account(conn, user["id"], "Personal", "personal", 0, None, None, None)
    else:
        personal_id = personal["id"]
    existing = {row["name"]: row["id"] for row in db.accounts(conn, user["id"])}
    if "Sample Prop" in existing:
        prop_id = existing["Sample Prop"]
    else:
        prop_id = db.insert_account(conn, user["id"], "Sample Prop", "prop", 50000, 1000, 2000, 3000)
    items = [item for item in db.checklist(conn, user["id"]) if item["active"]]

    def checks(count: int) -> list[dict]:
        return [
            {"item_id": item["id"], "checked": 1 if index < count else 0}
            for index, item in enumerate(items)
        ]

    def put(moment: datetime, **kwargs) -> None:
        qty = kwargs["qty"]
        legs = [Leg("entry", qty, kwargs["entry"], moment)]
        if kwargs.get("exit") is not None:
            legs.append(Leg("exit", qty, kwargs["exit"], moment + timedelta(minutes=kwargs.get("hold", 40))))
        chosen = checks(kwargs.get("checked", 0))
        auto = grade_for(sum(row["checked"] for row in chosen), len(chosen))
        fields, leg_rows = compose(
            zone=zone,
            instrument=kwargs["instrument"],
            asset_class="future",
            direction=kwargs["direction"],
            fees=kwargs.get("fees", 0),
            legs=legs,
            account_id=kwargs["account_id"],
            stop=kwargs.get("stop"),
            target=kwargs.get("target"),
            mae=kwargs.get("mae"),
            mfe=kwargs.get("mfe"),
            setup=kwargs.get("setup", ""),
            grade=auto,
            auto_grade=auto,
            htf_bias=kwargs.get("bias", ""),
            draw=kwargs.get("draw", ""),
            premium=kwargs.get("premium", ""),
            went_right=kwargs.get("went_right", ""),
            went_wrong=kwargs.get("went_wrong", ""),
            lesson=kwargs.get("lesson", ""),
            notes=SAMPLE_NOTE,
            emotion_before=kwargs.get("emotion", ""),
            emotion_after=kwargs.get("emotion", ""),
            confidence=kwargs.get("confidence"),
            followed_plan=kwargs.get("plan"),
        )
        save_trade(
            conn,
            user["id"],
            {
                "trade": fields,
                "legs": leg_rows,
                "tags": kwargs.get("tags", []),
                "mistakes": kwargs.get("mistakes", []),
                "checks": chosen,
            },
        )

    for day in past[0:4]:
        put(
            datetime(day.year, day.month, day.day, 9, 45, tzinfo=NY),
            instrument="MES",
            direction="long",
            qty=2,
            entry=5000,
            exit=5010,
            stop=4990,
            target=5020,
            mae=4996,
            mfe=5020,
            fees=2.5,
            account_id=personal_id,
            checked=len(items),
            tags=["FVG"],
            emotion="Calm",
            plan=1,
            confidence=7,
            setup="NY AM FVG",
            bias="Bullish",
            draw="BSL",
            premium="Discount",
            went_right="Entry was in the FVG during NY AM.",
            lesson="Waited for the FVG in NY AM.",
        )
    for index, day in enumerate(past[4:8]):
        put(
            datetime(day.year, day.month, day.day, 3, 20, tzinfo=NY),
            instrument="NQ",
            direction="short",
            qty=1,
            entry=20000,
            exit=20002,
            stop=19990,
            fees=2,
            account_id=prop_id,
            checked=min(4, len(items)),
            emotion="Anxious",
            plan=0 if index == 0 else 1,
            confidence=4,
            mistakes=["FOMO"] if index == 0 else [],
            bias="Bearish",
            draw="SSL",
            premium="Premium",
            went_wrong="Took it outside the written plan." if index == 0 else "London did not pay.",
            lesson="London was outside the plan.",
        )
    event = next((row for row in db.news_events(conn) if row["title"] == "Housing Starts"), None)
    if event:
        when = parse_iso(event["when_utc"]) - timedelta(minutes=10)
        if today - timedelta(days=21) <= when.astimezone(NY).date() <= today:
            put(
                when,
                instrument="NQ",
                direction="short",
                qty=1,
                entry=20000,
                exit=20002,
                stop=19990,
                fees=2,
                account_id=prop_id,
                checked=min(4, len(items)),
                emotion="Anxious",
                plan=0,
                confidence=3,
                mistakes=["Ignored news"],
                bias="Bearish",
                went_wrong="Opened ten minutes before Housing Starts.",
                lesson="High-impact news was inside the window.",
            )
    put(
        datetime(past[-1].year, past[-1].month, past[-1].day, 10, 5, tzinfo=NY),
        instrument="MNQ",
        direction="long",
        qty=1,
        entry=21000,
        stop=20980,
        account_id=personal_id,
        checked=len(items),
        emotion="Focused",
        plan=1,
        confidence=6,
        bias="Bullish",
        lesson="Still open. Review it after the exit.",
    )
    return "sample"
