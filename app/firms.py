"""Editable starting rules for the onboarding cards.

Figures are October 2026 50K shapes from public comparison desks, plus the
long-standing FTMO challenge percentages. They are a starting point in this
journal, and each field can be changed before it is saved.
"""

FIRMS = {
    "topstep": {
        "name": "Topstep Eval",
        "label": "Topstep",
        "mark": "TS",
        "starting": 50000,
        "daily": 1000,
        "trail": 2000,
        "target": 3000,
        "consistency": 55,
        "note": "50K Combine shape: $1,000 daily loss, $2,000 trailing max loss, $3,000 target, best day within 55%.",
    },
    "apex": {
        "name": "Apex Eval",
        "label": "Apex",
        "mark": "AX",
        "starting": 50000,
        "daily": 1000,
        "trail": 2000,
        "target": 3000,
        "consistency": 50,
        "note": "50K end-of-day shape: $2,000 trail, $1,000 daily loss, $3,000 target. Many Apex evals have no consistency rule; 50% is the funded check.",
    },
    "ftmo": {
        "name": "FTMO Eval",
        "label": "FTMO",
        "mark": "FT",
        "starting": 100000,
        "daily": 5000,
        "trail": 10000,
        "target": 10000,
        "consistency": None,
        "note": "100K challenge shape: 5% daily loss, 10% max loss, 10% target.",
    },
    "tradeify": {
        "name": "Tradeify Eval",
        "label": "Tradeify",
        "mark": "TY",
        "starting": 50000,
        "daily": None,
        "trail": 2000,
        "target": 3000,
        "consistency": 40,
        "note": "50K Select shape: $2,000 end-of-day trail, $3,000 target, best day within 40%. No daily loss on that plan.",
    },
    "mffu": {
        "name": "MyFundedFutures Eval",
        "label": "MyFundedFutures",
        "mark": "MF",
        "starting": 50000,
        "daily": None,
        "trail": 2000,
        "target": 3000,
        "consistency": 50,
        "note": "50K Pro shape: $2,000 end-of-day trail, $3,000 target, best day within 50%. No daily loss on that plan.",
    },
}
