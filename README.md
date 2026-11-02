# Omensite Journal

A private trade journal for one trader at a time. Log a fill, tag it with the ICT concepts you actually used, and read the pattern across your own history.

It does not send orders, publish a feed, or tell you what to trade. Broker auto-sync and an AI review are not in this version.

This is the current server-backed website and journal, including the public pages, Discord sign-in, and read-only demo. The earlier browser-only journal (`index.html`, `app.js`, and `style.css`) remains in the repository for existing browser-local installations. Run the current version with the Python server below; a static host such as GitHub Pages cannot run its server routes.

## Run it

From this folder:

```
py -3 -m pip install -r requirements.txt
omensite-journal.cmd
```

Or:

```
py -3 -m uvicorn app.main:app --host 127.0.0.1 --port 8787
```

Open http://127.0.0.1:8787. Discord is the only sign-in and sign-up method. Your first Discord sign-in creates your journal. You can also use Try the demo without signing in. Each login sees only its own journal.

Discord needs a Discord application, the redirect `http://127.0.0.1:8787/auth/discord/callback`, and `OMENSITE_DISCORD_CLIENT_ID` plus `OMENSITE_DISCORD_CLIENT_SECRET`. Those two lines can also live in `data/discord.env`. Until those values exist, the Discord button answers that sign-in is not configured.

The journal file stays on this machine.

The server listens on this machine only. To reach it from another device, bind a wider address on purpose, for example `--host 0.0.0.0`, and treat that machine as the one holding the data.

## What is included

- Trade logging for ES, NQ, MES, MNQ, YM, RTY, CL, GC, and stocks, including scale-ins and partial exits
- Net P&L, points, ticks, R, planned R, hold time, and MAE/MFE
- Topstep CSV import (the only currently supported broker), plus manual fill entry
- Chart slots for higher-timeframe context, entry, and after the exit, with markup
- ICT tags, a checklist that grades A+ / A / B / C, and a short review on each trade
- White and lime branding across public pages and the journal, with shared dashboard and calendar components
- A read-only demo and homepage preview backed by the same sample trades, with matching P&L totals and days off
- Dashboard, monthly P&L calendar, plain-language notes, rule-break cost, and profit left on the table
- Prop-account limits: daily loss, trailing drawdown, and target progress
- A built-in news snapshot for autumn 2026, plus holidays and early closes
- Emotion and mistake tags, a daily plan, and weekly and monthly review pages
- A playbook for your own setups
- CSV export, a JSON backup, and a print view (use the browser's Save as PDF)

## What is not included

- No broker connection. Import a CSV or type the fill.
- No AI review of the checklist.
- The TradingView box is a chart for the fill you logged. Scroll it back to the entry time shown on the trade.
- The news tab is a snapshot stored with the app, not a live calendar. Figures that were not sourced are left blank.

## Where the data lives

SQLite and chart images sit in the `data` folder next to this file. Set `OMENSITE_DATA` to put that folder somewhere else. Any device that can open this server sees the same journal. That is the sync: one server, one file.

## Tests

```
py -3 -m unittest discover -s tests -t .
```
