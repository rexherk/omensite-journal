"""Format numbers and draw the equity line from our own figures."""

from __future__ import annotations

import math

from app.calc import hold_label


def money(value) -> str:
    if value is None or value == "":
        return "—"
    number = float(value)
    if not math.isfinite(number):
        return "—"
    sign = "-" if number < 0 else ""
    return f"{sign}${abs(number):,.2f}"


def pnl_class(value) -> str:
    """Use the same gain/loss colors for money and realized risk/reward."""
    if value is None or value == "":
        return "neutral"
    number = float(value)
    if not math.isfinite(number) or number == 0:
        return "neutral"
    return "positive" if number > 0 else "negative"


def rmult(value) -> str:
    if value is None or value == "":
        return "—"
    number = float(value)
    if not math.isfinite(number):
        return "—"
    return f"{number:+.2f}R"


def pct(value) -> str:
    if value is None or value == "":
        return "—"
    number = float(value)
    if not math.isfinite(number):
        return "—"
    return f"{number * 100:.1f}%"


def factor(value) -> str:
    if value is None or value == "":
        return "—"
    number = float(value)
    if not math.isfinite(number):
        return "—"
    return f"{number:.2f}"


def plain(value) -> str:
    if value is None or value == "":
        return ""
    number = float(value)
    if not math.isfinite(number):
        return ""
    return f"{number:.6f}".rstrip("0").rstrip(".")


def hold(value) -> str:
    if value is None or value == "":
        return "Open"
    return hold_label(int(value))


def equity_svg(curve: list[dict]) -> str:
    if len(curve) < 2:
        return ""
    values = []
    for point in curve:
        number = float(point["equity"])
        if not math.isfinite(number):
            return ""
        values.append(number)
    width, height, pad = 640, 180, 16
    low = min(values + [0.0])
    high = max(values + [0.0])
    span = high - low or 1.0

    def x_at(index: int) -> float:
        return pad + (width - 2 * pad) * (index / (len(values) - 1))

    def y_at(number: float) -> float:
        return pad + (height - 2 * pad) * (1 - (number - low) / span)

    commands = []
    for index, number in enumerate(values):
        prefix = "M" if index == 0 else "L"
        commands.append(f"{prefix}{x_at(index):.1f},{y_at(number):.1f}")
    zero = y_at(0.0)
    color = {"positive": "var(--oj-gain)", "negative": "var(--oj-loss)",
             "neutral": "var(--oj-muted)"}[pnl_class(values[-1])]
    path = " ".join(commands)
    return (
        f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="Equity curve">'
        f'<line x1="{pad}" y1="{zero:.1f}" x2="{width - pad}" y2="{zero:.1f}" stroke="var(--chart-grid)"/>'
        f'<path d="{path}" fill="none" stroke="{color}" stroke-width="2"/>'
        "</svg>"
    )
