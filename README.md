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

Open http://127.0.0.1:8787. Visitors without an active session land on the login page; signed-in traders and active demo sessions return to their dashboard. The public product page remains at `/home`. Discord is the only sign-in and sign-up method. Your first Discord sign-in creates your journal. You can also use Try the demo without signing in. Each login sees only its own journal.

Discord needs a Discord application, the redirect `http://127.0.0.1:8787/auth/discord/callback`, and `OMENSITE_DISCORD_CLIENT_ID` plus `OMENSITE_DISCORD_CLIENT_SECRET`. Those two lines can also live in `data/discord.env`. Until those values exist, the Discord button answers that sign-in is not configured.

The journal file stays on this machine.

The server listens on this machine only. To reach it from another device, bind a wider address on purpose, for example `--host 0.0.0.0`, and treat that machine as the one holding the data.

## Managed hosting

The root `Dockerfile` runs the current FastAPI website on `0.0.0.0:$PORT` (8080 by default). Set the readiness path to `/health`. The container requires a managed PostgreSQL connection in `DATABASE_URL`; it refuses to use temporary SQLite storage when that connection is missing.

The PostgreSQL schema and additive account-rule migration are checked in under `migrations/`. Startup applies unapplied migrations inside a transaction, guarded by an advisory lock. You can also run `python -m app.migrate` explicitly. Applied versions are recorded in `schema_migrations`; existing account and trade records are preserved.

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
- An automatically displayed Tradays economic calendar, plus recent saved release highlights, holidays, and early closes
- Emotion and mistake tags, a daily plan, and monthly reviews that update as soon as a month is selected
- A playbook for your own setups
- CSV export, a JSON backup, and a print view (use the browser's Save as PDF)

Reviews use `GET /reviews?month=YYYY-MM` and group closed trades in the journal's current timezone; legacy week parameters are ignored. Monthly Report uses `GET /report?month=YYYY-MM` and shows that month's trades across all of the user's accounts, grouped by entry date in that same timezone. It defaults to the current month, including older `month=all` links. The month-named report has no all-time overview or notes, and its Print/PDF action is below the trade list.

The Import page includes the TopstepX export instructions. Select a Journal account before Preview; the selection carries to confirmation. `POST /import/preview` accepts the CSV `file`, the owned `account_id`, and the session's `csrf` token. `POST /import/confirm` accepts the preview `token`, the selected `account_id`, and `csrf`; both validate account ownership. Export one account at a time and avoid overlapping files because imports do not deduplicate repeated fills.

Brand colors live in `static/css/brand.css`: raspberry `#AB2059`, deep plum `#560641`, warm ochre `#BB7B3E`, red-orange `#E13823`, and crimson `#C9203C`. Cream framing and white data surfaces support readable plum text. Crescent-shaped background accents share the logo's raspberry–crimson–red-orange blend across public pages and the journal, with static gradients in the hero and call to action. Decorative layers do not intercept input and are omitted from print. Profit indicators use plum and loss indicators use crimson, with signs and labels alongside color. Performance calendar days use separate semantic tokens for subtle green profits and subtle red losses, with white days for no trades. The transparent logo uses a blended crescent with a solid ochre eye, candles, and trend arrow. The source mask clips all color to the design, without an expanded outer outline. The candle cutouts embedded in the crescent are filled to smooth its edge. The original image mask and local crescent repair are kept in `static/brand-mark.svg`; `static/brand-mark.png` is the tightly cropped 256-pixel website export and `static/brand-mark-1024.png` is the transparent high-resolution PNG download.

## What is not included

- No broker connection. Import a CSV or type the fill.
- No AI review of the checklist.
- The TradingView box is a chart for the fill you logged. Scroll it back to the entry time shown on the trade.
- Saved news releases come from a snapshot stored with the app. Missing figures are left blank.

## Where the data lives

Demo Combine names use `Topstep 50K Combine #XXXX123`, identified by their stable masked account number rather than a sequence number. Older demo names are renamed in place without replacing accounts or trades.

The dashboard's Account dropdown filters by saved account ID, with account and timeframe controls between the summary cards and calendar. Timeframe controls apply only to All Accounts and simulated accounts. Other account selections show full history, including when opened from an older range-filtered link. The Equity view plots each closed trade in the journal's configured timezone. Verified Combines use account balances on the USD axis, with target and loss-floor lines. Other selections use cumulative net P&L. Realized drawdown is shaded between the curve and its previous peak in the same graph. Exact net P&L and drawdown remain available in trade tooltips. The same model is available to authenticated users at `GET /api/dashboard/equity?account=<id>&range=all` (also `7d`, `30d`, and `mtd`), with private, non-cacheable responses.

Topstep overlays require a confirmed plan under Settings → Accounts → Plan and limits. The supported profiles are the standard 50K/100K/150K end-of-day trailing Combine and the 50K Static Combine, verified against Topstep's published rules on November 14, 2026. Unconfirmed or conflicting settings suppress overlays. All Accounts never inherits a single account's limits. Range-relative P&L uses the full account history to calculate the loss floor and drawdown. These calculations use recorded closed trades, so they cannot establish intratrade or unrealized-P&L compliance. Migration `002_account_rules_postgres.sql` adds an optional plan field without changing existing trade records.

Without `DATABASE_URL`, the local journal uses SQLite in the `data` folder next to this file. Set `OMENSITE_DATA` to put that folder somewhere else. New uploaded images are stored inside the selected database; existing local chart files remain supported. Each signed-in trader sees only their own records.

## Tests

```
py -3 -m unittest discover -s tests -t .
```
