"""ICT vocabulary, sessions, and the default pre-trade checklist."""

from __future__ import annotations

MARKUP_COLORS = ("#ab2059", "#560641", "#bb7b3e", "#e13823", "#c9203c")

TAGS = [
    "FVG",
    "Order Block",
    "Breaker",
    "Mitigation Block",
    "Buy-side liquidity sweep",
    "Sell-side liquidity sweep",
    "MSS",
    "BOS",
    "OTE",
    "Silver Bullet",
    "Judas Swing",
    "Power of 3",
    "SMT divergence",
    "NWOG",
    "NDOG",
]

MISTAKES = [
    "FOMO",
    "Revenge trade",
    "Moved stop",
    "Oversized",
    "Early exit",
    "Overtrading",
    "Chased",
    "No stop",
    "Late entry",
    "Ignored news",
]

EMOTIONS = [
    "Calm",
    "Focused",
    "Confident",
    "Anxious",
    "Impatient",
    "Fearful",
    "Frustrated",
    "Angry",
    "Euphoric",
    "Bored",
]

BIASES = ["Bullish", "Bearish", "Neutral"]

PREMIUM = ["Premium", "Discount", "Equilibrium"]

DRAWS = [
    "BSL",
    "SSL",
    "PDH",
    "PDL",
    "PWH",
    "PWL",
    "EQH",
    "EQL",
    "Asia high",
    "Asia low",
    "London high",
    "London low",
    "NY high",
    "NY low",
    "Session high",
    "Session low",
]

SESSIONS = ["Asia", "London", "NY AM", "NY PM"]

GRADES = ["A+", "A", "B", "C"]

DEFAULT_CHECKS = [
    "Higher-timeframe bias is written down",
    "Draw on liquidity is marked",
    "Dealing range and premium or discount are marked",
    "Entry is at a tagged ICT concept",
    "Entry is inside a kill zone or macro",
    "Stop is defined before entry",
    "Target is a liquidity pool",
    "Size matches the plan",
    "No high-impact news inside my window",
    "I am not in a revenge or FOMO state",
]

ACCOUNT_KINDS = ["personal", "prop", "sim"]

SHOT_SLOTS = [
    ("htf", "HTF context"),
    ("entry", "Entry"),
    ("after_exit", "After exit"),
]

KILL_ZONES = [
    "London Silver Bullet",
    "NY AM Silver Bullet",
    "NY PM Silver Bullet",
    "London Open",
    "NY AM",
    "NY PM",
    "Asia",
    "None",
]

MACROS = [
    "02:33-03:00",
    "04:03-04:30",
    "09:50-10:10",
    "10:50-11:10",
    "11:50-12:10",
    "13:10-13:40",
    "15:15-15:45",
    "None",
]

ZONES = [
    "America/New_York",
    "America/Chicago",
    "America/Denver",
    "America/Phoenix",
    "America/Los_Angeles",
    "America/Anchorage",
    "Pacific/Honolulu",
    "UTC",
    "Europe/London",
    "Europe/Berlin",
    "Asia/Tokyo",
    "Asia/Hong_Kong",
    "Asia/Singapore",
    "Australia/Sydney",
]
