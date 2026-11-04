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

## Managed hosting

The root `Dockerfile` runs the current FastAPI website on `0.0.0.0:$PORT` (8080 by default). Set the readiness path to `/health`. The container requires a managed PostgreSQL connection in `DATABASE_URL`; it refuses to use temporary SQLite storage when that connection is missing.

The PostgreSQL schema is checked in at `migrations/001_initial_postgres.sql`. Startup applies unapplied migrations inside a transaction, guarded by an advisory lock. You can also run `python -m app.migrate` explicitly. The migration is additive and records its version in `schema_migrations`.

Use the hosting platform's database attachment to inject `DATABASE_URL` over its private network. Native attachment requires current write access to both the database and repository server; either resource may be shared with you and they may have different owners. Shared connections remain active while that access remains valid. Revealing native connection credentials remains restricted to the database owner.

Set `OMENSITE_DISCORD_CLIENT_ID` and `OMENSITE_DISCORD_CLIENT_SECRET` in the server's encrypted environment. Register the public address followed by `/auth/discord/callback` on that Discord application, for example `https://journal.omensite.com/auth/discord/callback`.

Trades, accounts, sessions, notes, and uploaded chart images are stored in the database. Temporary CSV import previews use `OMENSITE_DATA`; users can upload the CSV again if a deployment interrupts a preview. Existing local image files remain readable and are included in JSON backups. Back up an existing database before future schema changes; application image rollback does not roll back database changes.

## What is included

- Trade logging for ES, NQ, MES, MNQ, YM, RTY, CL, GC, and stocks, including scale-ins and partial exits
- Net P&L, points, ticks, R, planned R, hold time, and MAE/MFE
- Topstep CSV import (the only currently supported broker), plus manual fill entry
- Chart slots for higher-timeframe context, entry, and after the exit, with markup
- ICT tags, a checklist that grades A+ / A / B / C, and a short review on each trade
- Raspberry, deep plum, warm ochre, red-orange, and crimson branding across public pages and the journal, with shared dashboard and calendar components
- A read-only demo and homepage preview backed by the same sample trades, with matching P&L totals and days off
- Dashboard, monthly P&L calendar, plain-language notes, rule-break cost, and profit left on the table
- Prop-account limits: daily loss, trailing drawdown, and target progress
- A built-in news snapshot for autumn 2026, plus holidays and early closes
- Emotion and mistake tags, a daily plan, and weekly and monthly review pages
- A playbook for your own setups
- CSV export, a JSON backup, and a print view (use the browser's Save as PDF)

Brand colors live in `static/css/brand.css`: raspberry `#AB2059`, deep plum `#560641`, warm ochre `#BB7B3E`, red-orange `#E13823`, and crimson `#C9203C`. Cream framing and white data surfaces support readable plum text. Profit indicators use plum and loss indicators use crimson, with signs and labels alongside color. Performance calendar days use separate semantic tokens for subtle green profits and subtle red losses, with white days for no trades. The transparent logo uses solid ochre candles and trend arrow, matching blended crescent and eye colors, and a deep plum outline. It preserves the original image mask in `static/brand-mark.svg`; `static/brand-mark.png` is the tightly cropped 256-pixel website export.

## What is not included

- No broker connection. Import a CSV or type the fill.
- No AI review of the checklist.
- The TradingView box is a chart for the fill you logged. Scroll it back to the entry time shown on the trade.
- The news tab is a snapshot stored with the app, not a live calendar. Figures that were not sourced are left blank.

## Where the data lives

Without `DATABASE_URL`, the local journal uses SQLite in the `data` folder next to this file. Set `OMENSITE_DATA` to put that folder somewhere else. New uploaded images are stored inside the selected database; existing local chart files remain supported. Each signed-in trader sees only their own records.

## Tests

```
py -3 -m unittest discover -s tests -t .
```
