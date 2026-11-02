"""Built-in economic snapshot for autumn 2026.

Times are New York local clocks converted to UTC when the database is seeded.
Figures are only the ones gathered for this snapshot. Blank cells were not stored.
This is not a live calendar.
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")
UTC = ZoneInfo("UTC")

CAVEAT = (
    "GDP and Core PCE have been listed on both October 29 and October 30 by different calendars. "
    "Confirm the BEA time before you treat either morning as a release. "
    "This tab is a built-in snapshot, not a live feed."
)

# month, day, hour, minute, title, impact, actual, forecast, previous, note
_ECONOMIC = [
    (10, 14, 8, 30, "CPI m/m", "high", "+0.65%", "", "", "September CPI, released October 14."),
    (10, 14, 8, 30, "Core CPI m/m", "high", "+0.33%", "", "", "September core CPI, released October 14."),
    (10, 15, 8, 30, "PPI m/m", "high", "", "", "", "Usual 8:30 a.m. ET BLS slot. No figure is stored here."),
    (10, 16, 8, 30, "Retail sales m/m", "high", "", "", "", "Usual 8:30 a.m. ET Census slot. No figure is stored here."),
    (10, 19, 10, 0, "NAHB Housing Market Index", "medium", "29", "32", "32", ""),
    (10, 19, 11, 30, "3-Month Bill Auction", "low", "", "", "", ""),
    (10, 19, 11, 30, "6-Month Bill Auction", "low", "", "", "", ""),
    (10, 20, 8, 15, "ADP Weekly Employment", "medium", "18.5K", "", "24.75K", ""),
    (10, 20, 8, 30, "Building Permits", "high", "1.40M", "1.39M", "", ""),
    (10, 20, 8, 30, "Housing Starts", "high", "1.221M", "1.30M", "", ""),
    (10, 20, 8, 30, "Building Permits MoM", "medium", "", "", "", ""),
    (10, 20, 8, 30, "Housing Starts MoM", "medium", "", "", "", ""),
    (10, 20, 8, 55, "Redbook", "low", "", "", "", ""),
    (10, 20, 10, 0, "Pending Home Sales MoM", "medium", "-7.3%", "", "", ""),
    (10, 20, 11, 0, "Atlanta Fed GDPNow", "medium", "3.5%", "", "", ""),
    (10, 20, 16, 30, "API Weekly Crude Oil Stock", "medium", "-4.93M", "", "", ""),
    (10, 21, 7, 0, "MBA Mortgage Applications", "low", "", "", "", "About 7:00 a.m. ET."),
    (10, 21, 10, 30, "EIA Crude Oil Inventories", "medium", "-3.06M", "-0.8M", "", ""),
    (10, 21, 10, 30, "EIA Gasoline Inventories", "medium", "", "", "", ""),
    (10, 21, 11, 30, "17-Week Bill Auction", "low", "", "", "", ""),
    (10, 21, 13, 0, "20-Year Bond Auction", "low", "", "", "", ""),
    (
        10, 22, 8, 30, "Initial Jobless Claims", "high", "", "200K", "199K",
        "Marked high in this journal. Some calendars rank weekly claims as medium.",
    ),
    (10, 22, 8, 30, "Continuing Claims", "low", "", "", "", ""),
    (10, 22, 10, 0, "Leading Economic Index", "low", "", "-0.1%", "", ""),
    (10, 22, 10, 30, "Natural Gas Storage", "low", "", "", "", ""),
    (10, 22, 11, 0, "Kansas City Fed Manufacturing", "low", "", "", "", ""),
    (10, 23, 9, 45, "S&P Global Flash Manufacturing PMI", "medium", "", "55.3-55.5", "55.9", ""),
    (10, 23, 9, 45, "S&P Global Flash Services PMI", "medium", "", "58", "58.8", ""),
    (10, 23, 9, 45, "S&P Global Flash Composite PMI", "medium", "", "", "58.4", ""),
    (10, 23, 10, 0, "Michigan Consumer Sentiment (final)", "medium", "", "46.3", "", ""),
    (10, 23, 13, 0, "Baker Hughes Rig Count", "low", "", "", "", "About 1:00 p.m. ET."),
    (10, 27, 10, 0, "CB Consumer Confidence", "medium", "", "", "", ""),
    (10, 28, 14, 0, "FOMC Statement", "high", "", "", "", "October 27-28 meeting. Statement at 2:00 p.m. ET."),
    (10, 28, 14, 30, "FOMC Press Conference", "high", "", "", "", "2:30 p.m. ET."),
    (11, 6, 8, 30, "Nonfarm Payrolls", "high", "", "", "", "8:30 a.m. ET."),
]

_HOLIDAYS = [
    (1, 1, "New Year's Day"),
    (1, 19, "Martin Luther King Jr. Day"),
    (2, 16, "Presidents Day"),
    (4, 3, "Good Friday"),
    (5, 25, "Memorial Day"),
    (6, 19, "Juneteenth"),
    (7, 3, "Independence Day (observed)"),
    (9, 7, "Labor Day"),
    (11, 26, "Thanksgiving"),
    (12, 25, "Christmas"),
]

_EARLY = [
    (11, 25, "Day before Thanksgiving, early close 1:00 p.m. ET"),
    (12, 24, "Christmas Eve, early close 1:00 p.m. ET"),
]


def _stamp(month: int, day: int, hour: int, minute: int) -> str:
    moment = datetime(2026, month, day, hour, minute, tzinfo=NY)
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_events() -> list[dict]:
    rows = []
    for month, day, hour, minute, title, impact, actual, forecast, previous, note in _ECONOMIC:
        rows.append(
            {
                "title": title,
                "when_utc": _stamp(month, day, hour, minute),
                "impact": impact,
                "category": "economic",
                "actual": actual,
                "forecast": forecast,
                "previous": previous,
                "note": note,
            }
        )
    for month, day, title in _HOLIDAYS:
        rows.append(
            {
                "title": title,
                "when_utc": _stamp(month, day, 9, 30),
                "impact": "low",
                "category": "holiday",
                "actual": "",
                "forecast": "",
                "previous": "",
                "note": "NYSE closed. Date shown in New York.",
            }
        )
    for month, day, title in _EARLY:
        rows.append(
            {
                "title": title,
                "when_utc": _stamp(month, day, 13, 0),
                "impact": "low",
                "category": "early_close",
                "actual": "",
                "forecast": "",
                "previous": "",
                "note": "NYSE early close. Date shown in New York.",
            }
        )
    return rows
