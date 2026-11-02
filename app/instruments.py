"""Contract specs. Dollar values are per point, per contract, from the exchange tick."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Spec:
    symbol: str
    name: str
    asset_class: str
    tick: float
    point_value: float
    tv_symbol: str

    @property
    def tick_value(self) -> float:
        return self.point_value * self.tick


# Tick and point values are the standard full-size and micro contracts:
# ES 0.25 = $12.50, NQ 0.25 = $5, YM 1 = $5, RTY 0.10 = $5,
# CL 0.01 = $10, GC 0.10 = $10. Micros are 1/10 of the mini.
FUTURES: dict[str, Spec] = {
    "ES": Spec("ES", "E-mini S&P 500", "future", 0.25, 50.0, "CME_MINI:ES1!"),
    "NQ": Spec("NQ", "E-mini Nasdaq-100", "future", 0.25, 20.0, "CME_MINI:NQ1!"),
    "MES": Spec("MES", "Micro E-mini S&P 500", "future", 0.25, 5.0, "CME_MINI:MES1!"),
    "MNQ": Spec("MNQ", "Micro E-mini Nasdaq-100", "future", 0.25, 2.0, "CME_MINI:MNQ1!"),
    "YM": Spec("YM", "E-mini Dow", "future", 1.0, 5.0, "CBOT_MINI:YM1!"),
    "RTY": Spec("RTY", "E-mini Russell 2000", "future", 0.10, 50.0, "CME_MINI:RTY1!"),
    "CL": Spec("CL", "Crude oil", "future", 0.01, 1000.0, "NYMEX:CL1!"),
    "GC": Spec("GC", "Gold", "future", 0.10, 100.0, "COMEX:GC1!"),
}


_MONTHS = set("FGHJKMNQUVXZ")


def parse_symbol(raw: str) -> str:
    text = " ".join((raw or "").upper().split())
    if not text or len(text) > 16 or not all(ch.isalnum() or ch in ".-!" for ch in text):
        raise ValueError("Enter a symbol such as ES or AAPL.")
    return text


def future_root(symbol: str) -> str | None:
    """Map MESZ6, NQH2026, or ES1! onto the journal's root symbol."""
    if symbol in FUTURES:
        return symbol
    if symbol.endswith("1!") and symbol[:-2] in FUTURES:
        return symbol[:-2]
    for root in sorted(FUTURES, key=len, reverse=True):
        if not symbol.startswith(root):
            continue
        rest = symbol[len(root):]
        if len(rest) >= 2 and rest[0] in _MONTHS and rest[1:].isdigit():
            return root
    return None


def spec_for(asset_class: str, instrument: str) -> Spec:
    symbol = parse_symbol(instrument)
    if asset_class == "future":
        root = future_root(symbol)
        if root is None:
            known = ", ".join(FUTURES)
            raise ValueError(f"Futures in this journal are {known}. Contract months such as MESZ6 are saved as the root.")
        return FUTURES[root]
    if asset_class == "stock":
        return Spec(symbol, symbol, "stock", 0.01, 1.0, symbol)
    raise ValueError("Choose futures or stock.")
