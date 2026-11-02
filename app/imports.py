"""Turn broker CSV exports into journal fills.

Round-trip files become one trade per row. Fill files are paired FIFO until
the position is flat. Times without a zone are read in the trader's zone.
"""

from __future__ import annotations

import csv
import io
from datetime import datetime
from zoneinfo import ZoneInfo

from app.instruments import future_root, parse_symbol

_FORMATS = (
    "%Y-%m-%dT%H:%M:%S.%fZ",
    "%Y-%m-%dT%H:%M:%SZ",
    "%Y-%m-%dT%H:%M:%S%z",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d %H:%M:%S",
    "%m/%d/%Y %H:%M:%S",
    "%m/%d/%Y %I:%M:%S %p",
    "%m/%d/%Y %H:%M",
    "%m/%d/%Y %I:%M %p",
    "%m/%d/%Y",
    "%Y-%m-%d",
)

_ALIASES = {
    "symbol": ["symbol", "instrument", "contract", "product", "ticker", "name"],
    "side": ["side", "b/s", "buy/sell", "market pos.", "market pos", "action", "direction", "type", "trans code"],
    "qty": ["qty", "quantity", "size", "filled qty", "filled", "contracts", "filled quantity"],
    "entry_price": ["entry price", "avg open price", "avg entry price", "open price", "entryprice"],
    "exit_price": ["exit price", "avg close price", "avg exit price", "close price", "exitprice"],
    "price": ["fill price", "avg price", "average price", "price"],
    "entry_time": ["entry time", "open time", "entered at", "entry date", "opened at"],
    "exit_time": ["exit time", "close time", "exited at", "exit date", "closed at"],
    "time": ["filled time", "fill time", "activity date", "timestamp", "time", "date"],
    "fees": ["commission", "fees", "fee", "commissions"],
}


class ImportError(ValueError):
    """The file is not a recognized fill export."""


def parse_csv(text: str, zone: ZoneInfo) -> list[dict]:
    sample = text.lstrip("\ufeff")
    if not sample.strip():
        raise ImportError("The file is empty.")
    reader = csv.DictReader(io.StringIO(sample))
    if not reader.fieldnames:
        raise ImportError("The file needs a header row.")
    columns = {_canon(name): name for name in reader.fieldnames if name}
    mapped = {key: _find(columns, aliases) for key, aliases in _ALIASES.items()}
    rows = [row for row in reader if any((value or "").strip() for value in row.values())]
    if not rows:
        raise ImportError("The file has headers but no fills.")
    if mapped["entry_price"] and mapped["exit_price"] and mapped["symbol"]:
        return [_round_trip(row, mapped, zone) for row in rows]
    if mapped["symbol"] and mapped["side"] and mapped["price"] and (mapped["time"] or mapped["entry_time"]):
        fills = [_fill(row, mapped, zone) for row in rows]
        return _pair(fills)
    found = ", ".join(reader.fieldnames)
    raise ImportError(f"Unrecognized columns: {found}")


def _classify(raw: str) -> tuple[str, str]:
    symbol = parse_symbol(raw)
    root = future_root(symbol)
    if root:
        return root, "future"
    return symbol, "stock"


def _round_trip(row: dict, mapped: dict[str, str | None], zone: ZoneInfo) -> dict:
    symbol, asset = _classify(_cell(row, mapped["symbol"]))
    direction = _direction(_cell(row, mapped["side"]))
    qty = _number(_cell(row, mapped["qty"]) or "1", "size")
    entry = _number(_cell(row, mapped["entry_price"]), "entry price")
    exit_ = _number(_cell(row, mapped["exit_price"]), "exit price")
    opened, open_bare = _time(_cell(row, mapped["entry_time"]) or _cell(row, mapped["time"]), zone)
    closed, close_bare = _time(_cell(row, mapped["exit_time"]) or _cell(row, mapped["time"]), zone)
    fees = _number(_cell(row, mapped["fees"]) or "0", "fees")
    warnings = []
    if open_bare or close_bare:
        warnings.append("Time was missing, set to midnight.")
    return {
        "instrument": symbol,
        "asset_class": asset,
        "direction": direction,
        "fees": fees,
        "legs": [
            {"kind": "entry", "qty": qty, "price": entry, "filled_at": opened},
            {"kind": "exit", "qty": qty, "price": exit_, "filled_at": closed},
        ],
        "warnings": warnings,
    }


def _fill(row: dict, mapped: dict[str, str | None], zone: ZoneInfo) -> dict:
    symbol, _asset = _classify(_cell(row, mapped["symbol"]))
    side = _buy_sell(_cell(row, mapped["side"]))
    when, bare = _time(_cell(row, mapped["time"]) or _cell(row, mapped["entry_time"]), zone)
    return {
        "instrument": symbol,
        "side": side,
        "qty": _number(_cell(row, mapped["qty"]) or "1", "size"),
        "price": _number(_cell(row, mapped["price"]), "price"),
        "filled_at": when,
        "fees": _number(_cell(row, mapped["fees"]) or "0", "fees"),
        "date_only": bare,
    }


def _pair(fills: list[dict]) -> list[dict]:
    groups: dict[str, list[dict]] = {}
    for fill in fills:
        groups.setdefault(fill["instrument"], []).append(fill)
    trades: list[dict] = []
    for symbol, book in groups.items():
        book.sort(key=lambda fill: fill["filled_at"])
        position = 0.0
        direction = "long"
        legs: list[dict] = []
        fees = 0.0
        date_only = False
        for fill in book:
            signed = fill["qty"] if fill["side"] == "buy" else -fill["qty"]
            if abs(position) < 1e-6 or (position > 0 and signed > 0) or (position < 0 and signed < 0):
                if abs(position) < 1e-6:
                    direction = "long" if signed > 0 else "short"
                legs.append(_leg("entry", fill))
                position += signed
                fees += fill["fees"]
                date_only = date_only or fill["date_only"]
                continue
            closing = min(abs(position), abs(signed))
            leftover = abs(signed) - closing
            legs.append({"kind": "exit", "qty": closing, "price": fill["price"], "filled_at": fill["filled_at"]})
            fees += fill["fees"]
            date_only = date_only or fill["date_only"]
            position += closing if position < 0 else -closing
            if abs(position) < 1e-6:
                trades.append(_bundle(symbol, direction, legs, fees, date_only))
                legs = []
                fees = 0.0
                position = 0.0
                date_only = False
            if leftover > 1e-6:
                direction = "long" if fill["side"] == "buy" else "short"
                legs = [{"kind": "entry", "qty": leftover, "price": fill["price"], "filled_at": fill["filled_at"]}]
                position = leftover if fill["side"] == "buy" else -leftover
                date_only = bool(fill["date_only"])
        if legs:
            trades.append(_bundle(symbol, direction, legs, fees, date_only))
    if not trades:
        raise ImportError("No fills could be paired.")
    return trades


def _bundle(symbol: str, direction: str, legs: list[dict], fees: float, date_only: bool) -> dict:
    warnings = []
    if not any(leg["kind"] == "exit" for leg in legs):
        warnings.append("Still open when the file ended.")
    if date_only:
        warnings.append("Time was missing, set to midnight.")
    root = future_root(symbol)
    return {
        "instrument": root or symbol,
        "asset_class": "future" if root else "stock",
        "direction": direction,
        "fees": fees,
        "legs": legs,
        "warnings": warnings,
    }


def _leg(kind: str, fill: dict) -> dict:
    return {"kind": kind, "qty": fill["qty"], "price": fill["price"], "filled_at": fill["filled_at"]}


def _canon(name: str) -> str:
    return " ".join(name.strip().lower().replace("_", " ").split())


def _find(columns: dict[str, str], aliases: list[str]) -> str | None:
    for alias in aliases:
        if alias in columns:
            return columns[alias]
    return None


def _cell(row: dict, header: str | None) -> str:
    if not header:
        return ""
    return (row.get(header) or "").strip()


def _number(text: str, label: str) -> float:
    cleaned = text.replace("$", "").replace(",", "").strip()
    if cleaned in {"", "-"}:
        if label == "fees":
            return 0.0
        raise ImportError(f"A row is missing {label}.")
    try:
        return float(cleaned)
    except ValueError as exc:
        raise ImportError(f"{label} is not a number: {text}") from exc


def _direction(text: str) -> str:
    value = text.strip().lower()
    if value in {"long", "buy", "b", "bot"}:
        return "long"
    if value in {"short", "sell", "s", "sld"}:
        return "short"
    raise ImportError(f"Could not read side '{text}'.")


def _buy_sell(text: str) -> str:
    value = text.strip().lower()
    if value in {"buy", "b", "bot", "long"}:
        return "buy"
    if value in {"sell", "s", "sld", "short"}:
        return "sell"
    raise ImportError(f"Could not read side '{text}'.")


def _time(text: str, zone: ZoneInfo) -> tuple[datetime, bool]:
    raw = text.strip()
    if not raw:
        raise ImportError("A row is missing a time.")
    date_only = ":" not in raw
    if raw.endswith("Z"):
        for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ"):
            try:
                parsed = datetime.strptime(raw, fmt)
                return parsed.replace(tzinfo=ZoneInfo("UTC")), False
            except ValueError:
                continue
    for fmt in _FORMATS:
        try:
            parsed = datetime.strptime(raw, fmt)
        except ValueError:
            continue
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=zone)
        return parsed, date_only
    raise ImportError(f"Could not read the time '{text}'.")
