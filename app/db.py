"""SQLite locally, PostgreSQL when DATABASE_URL is configured. Rows are user-scoped."""

from __future__ import annotations

import sqlite3
import os
from pathlib import Path
from contextlib import contextmanager
from datetime import datetime
from zoneinfo import ZoneInfo

from app.news_data import build_events
from app.paths import db_path

UTC = ZoneInfo("UTC")

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    password_salt TEXT NOT NULL,
    timezone TEXT NOT NULL DEFAULT 'America/New_York',
    news_window_minutes INTEGER NOT NULL DEFAULT 15,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
    token TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    csrf TEXT NOT NULL,
    expires_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS accounts (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('personal', 'prop', 'sim')),
    starting_balance REAL NOT NULL DEFAULT 0,
    daily_loss_limit REAL,
    trailing_drawdown REAL,
    profit_target REAL,
    UNIQUE (user_id, name)
);
CREATE TABLE IF NOT EXISTS checklist_items (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    label TEXT NOT NULL,
    position INTEGER NOT NULL,
    active INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    account_id INTEGER NOT NULL REFERENCES accounts(id) ON DELETE RESTRICT,
    instrument TEXT NOT NULL,
    asset_class TEXT NOT NULL CHECK (asset_class IN ('future', 'stock')),
    direction TEXT NOT NULL CHECK (direction IN ('long', 'short')),
    fees REAL NOT NULL DEFAULT 0,
    stop REAL,
    target REAL,
    session TEXT,
    kill_zone TEXT,
    macro_window TEXT,
    htf_bias TEXT,
    draw TEXT,
    premium TEXT,
    range_high REAL,
    range_low REAL,
    setup TEXT,
    grade TEXT,
    auto_grade TEXT,
    grade_manual INTEGER NOT NULL DEFAULT 0,
    went_right TEXT,
    went_wrong TEXT,
    lesson TEXT,
    notes TEXT,
    emotion_before TEXT,
    emotion_after TEXT,
    confidence INTEGER,
    followed_plan INTEGER CHECK (followed_plan IS NULL OR followed_plan IN (0, 1)),
    mae_price REAL,
    mfe_price REAL,
    opened_at TEXT,
    closed_at TEXT,
    opened_local TEXT,
    closed_local TEXT,
    closed_day TEXT,
    is_closed INTEGER NOT NULL CHECK (is_closed IN (0, 1)),
    net_pnl REAL,
    gross_pnl REAL,
    points REAL,
    ticks REAL,
    r_multiple REAL,
    planned_r REAL,
    hold_seconds INTEGER,
    risk_dollars REAL,
    mae_points REAL,
    mfe_points REAL,
    mae_dollars REAL,
    mfe_dollars REAL,
    left_on_table REAL,
    avg_entry REAL,
    avg_exit REAL,
    qty_entered REAL,
    qty_exited REAL,
    open_qty REAL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS legs (
    id INTEGER PRIMARY KEY,
    trade_id INTEGER NOT NULL REFERENCES trades(id) ON DELETE CASCADE,
    position INTEGER NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('entry', 'exit')),
    qty REAL NOT NULL,
    price REAL NOT NULL,
    filled_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS trade_tags (
    trade_id INTEGER NOT NULL REFERENCES trades(id) ON DELETE CASCADE,
    tag TEXT NOT NULL,
    PRIMARY KEY (trade_id, tag)
);
CREATE TABLE IF NOT EXISTS trade_mistakes (
    trade_id INTEGER NOT NULL REFERENCES trades(id) ON DELETE CASCADE,
    mistake TEXT NOT NULL,
    PRIMARY KEY (trade_id, mistake)
);
CREATE TABLE IF NOT EXISTS trade_checks (
    trade_id INTEGER NOT NULL REFERENCES trades(id) ON DELETE CASCADE,
    item_id INTEGER NOT NULL REFERENCES checklist_items(id) ON DELETE CASCADE,
    checked INTEGER NOT NULL,
    PRIMARY KEY (trade_id, item_id)
);
CREATE TABLE IF NOT EXISTS screenshots (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    trade_id INTEGER NOT NULL REFERENCES trades(id) ON DELETE CASCADE,
    slot TEXT NOT NULL CHECK (slot IN ('htf', 'entry', 'after_exit')),
    filename TEXT NOT NULL,
    markup_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL,
    UNIQUE (trade_id, slot)
);
CREATE TABLE IF NOT EXISTS days (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    day TEXT NOT NULL,
    bias TEXT,
    key_levels TEXT,
    draw TEXT,
    news_to_watch TEXT,
    eod_review TEXT,
    UNIQUE (user_id, day)
);
CREATE TABLE IF NOT EXISTS playbooks (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    setup TEXT,
    rules TEXT,
    example_notes TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS playbook_images (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    playbook_id INTEGER NOT NULL REFERENCES playbooks(id) ON DELETE CASCADE,
    filename TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS watchlist (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    symbol TEXT NOT NULL,
    UNIQUE (user_id, symbol)
);
CREATE TABLE IF NOT EXISTS password_resets (
    token TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS earnings (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    symbol TEXT NOT NULL,
    when_at TEXT NOT NULL,
    note TEXT
);
CREATE TABLE IF NOT EXISTS news_events (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    when_utc TEXT NOT NULL,
    impact TEXT NOT NULL CHECK (impact IN ('high', 'medium', 'low')),
    category TEXT NOT NULL CHECK (category IN ('economic', 'holiday', 'early_close')),
    actual TEXT,
    forecast TEXT,
    previous TEXT,
    note TEXT
);
CREATE INDEX IF NOT EXISTS idx_trades_user ON trades (user_id, opened_at);
CREATE INDEX IF NOT EXISTS idx_news_when ON news_events (when_utc);
CREATE TABLE IF NOT EXISTS media_blobs (
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    filename TEXT NOT NULL,
    content BLOB NOT NULL,
    PRIMARY KEY (user_id, filename)
);
"""

TRADE_FIELDS = [
    "user_id",
    "account_id",
    "instrument",
    "asset_class",
    "direction",
    "fees",
    "stop",
    "target",
    "session",
    "kill_zone",
    "macro_window",
    "htf_bias",
    "draw",
    "premium",
    "range_high",
    "range_low",
    "setup",
    "grade",
    "auto_grade",
    "grade_manual",
    "went_right",
    "went_wrong",
    "lesson",
    "notes",
    "emotion_before",
    "emotion_after",
    "confidence",
    "followed_plan",
    "mae_price",
    "mfe_price",
    "opened_at",
    "closed_at",
    "opened_local",
    "closed_local",
    "closed_day",
    "is_closed",
    "net_pnl",
    "gross_pnl",
    "points",
    "ticks",
    "r_multiple",
    "planned_r",
    "hold_seconds",
    "risk_dollars",
    "mae_points",
    "mfe_points",
    "mae_dollars",
    "mfe_dollars",
    "left_on_table",
    "avg_entry",
    "avg_exit",
    "qty_entered",
    "qty_exited",
    "open_qty",
    "created_at",
]


def connect() -> sqlite3.Connection:
    url = os.environ.get("DATABASE_URL", "").strip()
    if url:
        if not url.startswith(("postgres://", "postgresql://")):
            raise RuntimeError("DATABASE_URL must be a PostgreSQL connection URL.")
        from app.postgres import PostgresConnection
        return PostgresConnection(url)
    if os.environ.get("OMENSITE_REQUIRE_DATABASE") == "1":
        raise RuntimeError("Attach a managed PostgreSQL database using DATABASE_URL before starting this deployment.")
    conn = sqlite3.connect(db_path(), timeout=5)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def session():
    conn = connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _column_names(conn: sqlite3.Connection, table: str) -> set[str]:
    if is_postgres(conn):
        return {row["name"] for row in conn.execute(
            "SELECT column_name AS name FROM information_schema.columns WHERE table_schema = current_schema() AND table_name = ?", (table,))}
    return {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}


def is_postgres(conn) -> bool:
    return not isinstance(conn, sqlite3.Connection)


def insert_id(conn, sql: str, args=()) -> int:
    if is_postgres(conn):
        return int(conn.execute(sql.strip().rstrip(";") + " RETURNING id", args).fetchone()["id"])
    return int(conn.execute(sql, args).lastrowid)


def ensure_user_columns(conn: sqlite3.Connection) -> None:
    have = _column_names(conn, "users")
    if "discord_id" not in have:
        conn.execute("ALTER TABLE users ADD COLUMN discord_id TEXT")
    if "display_name" not in have:
        conn.execute("ALTER TABLE users ADD COLUMN display_name TEXT")
    if "onboarded" not in have:
        conn.execute("ALTER TABLE users ADD COLUMN onboarded INTEGER NOT NULL DEFAULT 1")
    if "markets" not in have:
        conn.execute("ALTER TABLE users ADD COLUMN markets TEXT")
    if "google_id" not in have:
        conn.execute("ALTER TABLE users ADD COLUMN google_id TEXT")
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS users_discord_id ON users(discord_id) WHERE discord_id IS NOT NULL"
    )
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS users_google_id ON users(google_id) WHERE google_id IS NOT NULL"
    )
    accounts = _column_names(conn, "accounts")
    if "consistency_pct" not in accounts:
        conn.execute("ALTER TABLE accounts ADD COLUMN consistency_pct REAL")


def init_db(conn: sqlite3.Connection) -> None:
    if is_postgres(conn):
        # Serialize first-time setup across application workers.
        conn.execute("SELECT 1 FROM pg_advisory_xact_lock(654719032)")
        conn.execute("CREATE TABLE IF NOT EXISTS schema_migrations (version TEXT PRIMARY KEY, applied_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP)")
        version = "001_initial"
        if not conn.execute("SELECT version FROM schema_migrations WHERE version = ?", (version,)).fetchone():
            schema = Path(__file__).resolve().parent.parent / "migrations" / "001_initial_postgres.sql"
            conn.executescript(schema.read_text(encoding="utf-8"))
            conn.execute("INSERT INTO schema_migrations (version) VALUES (?)", (version,))
    else:
        conn.executescript(SCHEMA)
        ensure_user_columns(conn)
    count = conn.execute("SELECT COUNT(*) AS n FROM news_events").fetchone()["n"]
    if count:
        return
    rows = build_events()
    conn.executemany(
        """
        INSERT INTO news_events (title, when_utc, impact, category, actual, forecast, previous, note)
        VALUES (:title, :when_utc, :impact, :category, :actual, :forecast, :previous, :note)
        """,
        rows,
    )


def one(conn, sql: str, args=()) -> dict | None:
    row = conn.execute(sql, args).fetchone()
    return dict(row) if row else None


def many(conn, sql: str, args=()) -> list[dict]:
    return [dict(row) for row in conn.execute(sql, args).fetchall()]


def create_user(conn, email: str, salt: str, password_hash: str, timezone: str) -> int:
    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    return insert_id(conn,
        """
        INSERT INTO users (email, password_hash, password_salt, timezone, news_window_minutes, created_at)
        VALUES (?, ?, ?, ?, 15, ?)
        """,
        (email, password_hash, salt, timezone, now),
    )


def user_by_email(conn, email: str) -> dict | None:
    return one(conn, "SELECT * FROM users WHERE email = ?", (email,))


def user_by_discord(conn, discord_id: str) -> dict | None:
    return one(conn, "SELECT * FROM users WHERE discord_id = ?", (discord_id,))


def attach_discord(conn, user_id: int, discord_id: str, display_name: str) -> None:
    conn.execute(
        "UPDATE users SET discord_id = ?, display_name = ? WHERE id = ?",
        (discord_id, display_name, user_id),
    )


def user_by_google(conn, google_id: str) -> dict | None:
    return one(conn, "SELECT * FROM users WHERE google_id = ?", (google_id,))


def attach_google(conn, user_id: int, google_id: str, display_name: str) -> None:
    conn.execute(
        "UPDATE users SET google_id = ?, display_name = ? WHERE id = ?",
        (google_id, display_name, user_id),
    )


def user_by_id(conn, user_id: int) -> dict | None:
    return one(conn, "SELECT * FROM users WHERE id = ?", (user_id,))


def set_onboarded(conn, user_id: int, done: int) -> None:
    conn.execute("UPDATE users SET onboarded = ? WHERE id = ?", (1 if done else 0, user_id))


def set_markets(conn, user_id: int, markets: str) -> None:
    conn.execute("UPDATE users SET markets = ? WHERE id = ?", (markets, user_id))


def set_password(conn, user_id: int, salt: str, password_hash: str) -> None:
    conn.execute(
        "UPDATE users SET password_salt = ?, password_hash = ? WHERE id = ?",
        (salt, password_hash, user_id),
    )


def set_consistency(conn, user_id: int, account_id: int, pct: float | None) -> None:
    conn.execute(
        "UPDATE accounts SET consistency_pct = ? WHERE user_id = ? AND id = ?",
        (pct, user_id, account_id),
    )


def create_reset(conn, user_id: int, token: str, expires_at: str) -> None:
    conn.execute("DELETE FROM password_resets WHERE user_id = ?", (user_id,))
    conn.execute(
        "INSERT INTO password_resets (token, user_id, expires_at) VALUES (?, ?, ?)",
        (token, user_id, expires_at),
    )


def reset_row(conn, token: str) -> dict | None:
    return one(conn, "SELECT * FROM password_resets WHERE token = ?", (token,))


def delete_reset(conn, token: str) -> None:
    conn.execute("DELETE FROM password_resets WHERE token = ?", (token,))


def update_user(conn, user_id: int, timezone: str, window: int) -> None:
    conn.execute(
        "UPDATE users SET timezone = ?, news_window_minutes = ? WHERE id = ?",
        (timezone, window, user_id),
    )


def create_session(conn, user_id: int, token: str, csrf: str, expires_at: str) -> None:
    conn.execute(
        "INSERT INTO sessions (token, user_id, csrf, expires_at) VALUES (?, ?, ?, ?)",
        (token, user_id, csrf, expires_at),
    )


def delete_session(conn, token: str) -> None:
    conn.execute("DELETE FROM sessions WHERE token = ?", (token,))


def session_user(conn, token: str) -> dict | None:
    row = one(
        conn,
        """
        SELECT users.id, users.email, users.display_name, users.timezone, users.news_window_minutes,
               sessions.csrf, sessions.token, sessions.expires_at
        FROM sessions JOIN users ON users.id = sessions.user_id
        WHERE sessions.token = ?
        """,
        (token,),
    )
    if row is None:
        return None
    expires = datetime.fromisoformat(row["expires_at"].replace("Z", "+00:00"))
    if expires < datetime.now(UTC):
        conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
        return None
    return row


def accounts(conn, user_id: int) -> list[dict]:
    return many(conn, "SELECT * FROM accounts WHERE user_id = ? ORDER BY id", (user_id,))


def account(conn, user_id: int, account_id: int) -> dict | None:
    return one(conn, "SELECT * FROM accounts WHERE user_id = ? AND id = ?", (user_id, account_id))


def insert_account(conn, user_id, name, kind, starting, daily, trail, target) -> int:
    return insert_id(conn,
        """
        INSERT INTO accounts (user_id, name, kind, starting_balance, daily_loss_limit, trailing_drawdown, profit_target)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (user_id, name, kind, starting, daily, trail, target),
    )


def delete_account(conn, user_id: int, account_id: int) -> None:
    conn.execute("DELETE FROM accounts WHERE user_id = ? AND id = ?", (user_id, account_id))


def checklist(conn, user_id: int) -> list[dict]:
    return many(
        conn,
        "SELECT * FROM checklist_items WHERE user_id = ? ORDER BY position, id",
        (user_id,),
    )


def add_check(conn, user_id: int, label: str, position: int) -> int:
    return insert_id(conn,
        "INSERT INTO checklist_items (user_id, label, position, active) VALUES (?, ?, ?, 1)",
        (user_id, label, position),
    )


def disable_check(conn, user_id: int, item_id: int) -> None:
    conn.execute(
        "UPDATE checklist_items SET active = 0 WHERE user_id = ? AND id = ?",
        (user_id, item_id),
    )


def insert_trade(conn, fields: dict) -> int:
    keys = [key for key in TRADE_FIELDS if key in fields]
    marks = ", ".join("?" for _ in keys)
    return insert_id(conn,
        f"INSERT INTO trades ({', '.join(keys)}) VALUES ({marks})",
        [fields[key] for key in keys],
    )


def update_trade(conn, user_id: int, trade_id: int, fields: dict) -> bool:
    keys = [key for key in TRADE_FIELDS if key in fields and key not in {"user_id", "created_at"}]
    assignments = ", ".join(f"{key} = ?" for key in keys)
    values = [fields[key] for key in keys]
    values.extend([trade_id, user_id])
    cur = conn.execute(
        f"UPDATE trades SET {assignments} WHERE id = ? AND user_id = ?",
        values,
    )
    return cur.rowcount == 1


def delete_trade(conn, user_id: int, trade_id: int) -> bool:
    cur = conn.execute("DELETE FROM trades WHERE id = ? AND user_id = ?", (trade_id, user_id))
    return cur.rowcount == 1


def replace_children(conn, trade_id: int, legs: list[dict], tags: list[str], mistakes: list[str], checks: list[dict]) -> None:
    conn.execute("DELETE FROM legs WHERE trade_id = ?", (trade_id,))
    conn.execute("DELETE FROM trade_tags WHERE trade_id = ?", (trade_id,))
    conn.execute("DELETE FROM trade_mistakes WHERE trade_id = ?", (trade_id,))
    conn.execute("DELETE FROM trade_checks WHERE trade_id = ?", (trade_id,))
    conn.executemany(
        "INSERT INTO legs (trade_id, position, kind, qty, price, filled_at) VALUES (?, ?, ?, ?, ?, ?)",
        [(trade_id, index, leg["kind"], leg["qty"], leg["price"], leg["filled_at"]) for index, leg in enumerate(legs)],
    )
    conn.executemany(
        "INSERT INTO trade_tags (trade_id, tag) VALUES (?, ?)",
        [(trade_id, tag) for tag in tags],
    )
    conn.executemany(
        "INSERT INTO trade_mistakes (trade_id, mistake) VALUES (?, ?)",
        [(trade_id, mistake) for mistake in mistakes],
    )
    conn.executemany(
        "INSERT INTO trade_checks (trade_id, item_id, checked) VALUES (?, ?, ?)",
        [(trade_id, item["item_id"], item["checked"]) for item in checks],
    )


def trades(conn, user_id: int) -> list[dict]:
    return many(
        conn,
        """
        SELECT trades.*, accounts.name AS account_name, accounts.kind AS account_kind
        FROM trades JOIN accounts ON accounts.id = trades.account_id
        WHERE trades.user_id = ?
        ORDER BY COALESCE(trades.opened_at, trades.created_at) DESC, trades.id DESC
        """,
        (user_id,),
    )


def trade(conn, user_id: int, trade_id: int) -> dict | None:
    return one(
        conn,
        """
        SELECT trades.*, accounts.name AS account_name, accounts.kind AS account_kind
        FROM trades JOIN accounts ON accounts.id = trades.account_id
        WHERE trades.user_id = ? AND trades.id = ?
        """,
        (user_id, trade_id),
    )


def legs(conn, trade_id: int) -> list[dict]:
    return many(conn, "SELECT * FROM legs WHERE trade_id = ? ORDER BY position, id", (trade_id,))


def tags_for_user(conn, user_id: int) -> dict[int, list[str]]:
    rows = many(
        conn,
        """
        SELECT trades.id AS trade_id, trade_tags.tag
        FROM trade_tags JOIN trades ON trades.id = trade_tags.trade_id
        WHERE trades.user_id = ?
        ORDER BY trade_tags.tag
        """,
        (user_id,),
    )
    grouped: dict[int, list[str]] = {}
    for row in rows:
        grouped.setdefault(row["trade_id"], []).append(row["tag"])
    return grouped


def mistakes_for_user(conn, user_id: int) -> dict[int, list[str]]:
    rows = many(
        conn,
        """
        SELECT trades.id AS trade_id, trade_mistakes.mistake
        FROM trade_mistakes JOIN trades ON trades.id = trade_mistakes.trade_id
        WHERE trades.user_id = ?
        ORDER BY trade_mistakes.mistake
        """,
        (user_id,),
    )
    grouped: dict[int, list[str]] = {}
    for row in rows:
        grouped.setdefault(row["trade_id"], []).append(row["mistake"])
    return grouped


def checks_for_trade(conn, trade_id: int) -> list[dict]:
    return many(
        conn,
        """
        SELECT trade_checks.item_id, trade_checks.checked, checklist_items.label, checklist_items.active
        FROM trade_checks JOIN checklist_items ON checklist_items.id = trade_checks.item_id
        WHERE trade_checks.trade_id = ?
        ORDER BY checklist_items.position, checklist_items.id
        """,
        (trade_id,),
    )


def shots(conn, trade_id: int) -> list[dict]:
    return many(conn, "SELECT * FROM screenshots WHERE trade_id = ? ORDER BY id", (trade_id,))


def shot(conn, user_id: int, shot_id: int) -> dict | None:
    return one(conn, "SELECT * FROM screenshots WHERE user_id = ? AND id = ?", (user_id, shot_id))


def upsert_shot(conn, user_id: int, trade_id: int, slot: str, filename: str, created_at: str) -> int:
    existing = one(
        conn,
        "SELECT * FROM screenshots WHERE trade_id = ? AND slot = ?",
        (trade_id, slot),
    )
    if existing:
        conn.execute(
            "UPDATE screenshots SET filename = ?, markup_json = '[]', created_at = ? WHERE id = ?",
            (filename, created_at, existing["id"]),
        )
        return int(existing["id"])
    return insert_id(conn,
        """
        INSERT INTO screenshots (user_id, trade_id, slot, filename, markup_json, created_at)
        VALUES (?, ?, ?, ?, '[]', ?)
        """,
        (user_id, trade_id, slot, filename, created_at),
    )


def set_markup(conn, user_id: int, shot_id: int, markup_json: str) -> bool:
    cur = conn.execute(
        "UPDATE screenshots SET markup_json = ? WHERE user_id = ? AND id = ?",
        (markup_json, user_id, shot_id),
    )
    return cur.rowcount == 1


def delete_shot(conn, user_id: int, shot_id: int) -> dict | None:
    row = shot(conn, user_id, shot_id)
    if row is None:
        return None
    conn.execute("DELETE FROM screenshots WHERE id = ? AND user_id = ?", (shot_id, user_id))
    return row


def day_row(conn, user_id: int, day: str) -> dict | None:
    return one(conn, "SELECT * FROM days WHERE user_id = ? AND day = ?", (user_id, day))


def save_day(conn, user_id: int, day: str, bias: str, levels: str, draw: str, news: str, review: str) -> None:
    conn.execute(
        """
        INSERT INTO days (user_id, day, bias, key_levels, draw, news_to_watch, eod_review)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(user_id, day) DO UPDATE SET
            bias = excluded.bias,
            key_levels = excluded.key_levels,
            draw = excluded.draw,
            news_to_watch = excluded.news_to_watch,
            eod_review = excluded.eod_review
        """,
        (user_id, day, bias, levels, draw, news, review),
    )


def playbooks(conn, user_id: int) -> list[dict]:
    return many(conn, "SELECT * FROM playbooks WHERE user_id = ? ORDER BY id DESC", (user_id,))


def playbook(conn, user_id: int, playbook_id: int) -> dict | None:
    return one(conn, "SELECT * FROM playbooks WHERE user_id = ? AND id = ?", (user_id, playbook_id))


def insert_playbook(conn, user_id: int, name: str, setup: str, rules: str, notes: str, created_at: str) -> int:
    return insert_id(conn,
        """
        INSERT INTO playbooks (user_id, name, setup, rules, example_notes, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (user_id, name, setup, rules, notes, created_at),
    )


def update_playbook(conn, user_id: int, playbook_id: int, name: str, setup: str, rules: str, notes: str) -> bool:
    cur = conn.execute(
        """
        UPDATE playbooks SET name = ?, setup = ?, rules = ?, example_notes = ?
        WHERE user_id = ? AND id = ?
        """,
        (name, setup, rules, notes, user_id, playbook_id),
    )
    return cur.rowcount == 1


def delete_playbook(conn, user_id: int, playbook_id: int) -> bool:
    cur = conn.execute("DELETE FROM playbooks WHERE user_id = ? AND id = ?", (user_id, playbook_id))
    return cur.rowcount == 1


def playbook_images(conn, playbook_id: int) -> list[dict]:
    return many(conn, "SELECT * FROM playbook_images WHERE playbook_id = ? ORDER BY id", (playbook_id,))


def playbook_image(conn, user_id: int, image_id: int) -> dict | None:
    return one(conn, "SELECT * FROM playbook_images WHERE user_id = ? AND id = ?", (user_id, image_id))


def add_playbook_image(conn, user_id: int, playbook_id: int, filename: str, created_at: str) -> int:
    return insert_id(conn,
        "INSERT INTO playbook_images (user_id, playbook_id, filename, created_at) VALUES (?, ?, ?, ?)",
        (user_id, playbook_id, filename, created_at),
    )


def delete_playbook_image(conn, user_id: int, image_id: int) -> dict | None:
    row = playbook_image(conn, user_id, image_id)
    if row is None:
        return None
    conn.execute("DELETE FROM playbook_images WHERE id = ? AND user_id = ?", (image_id, user_id))
    return row


def watch_rows(conn, user_id: int) -> list[dict]:
    return many(conn, "SELECT * FROM watchlist WHERE user_id = ? ORDER BY symbol", (user_id,))


def add_watch(conn, user_id: int, symbol: str) -> None:
    conn.execute("INSERT INTO watchlist (user_id, symbol) VALUES (?, ?) ON CONFLICT(user_id, symbol) DO NOTHING", (user_id, symbol))


def delete_watch(conn, user_id: int, watch_id: int) -> None:
    conn.execute("DELETE FROM watchlist WHERE user_id = ? AND id = ?", (user_id, watch_id))


def earning_rows(conn, user_id: int) -> list[dict]:
    return many(conn, "SELECT * FROM earnings WHERE user_id = ? ORDER BY when_at", (user_id,))


def add_earning(conn, user_id: int, symbol: str, when_at: str, note: str) -> None:
    conn.execute(
        "INSERT INTO earnings (user_id, symbol, when_at, note) VALUES (?, ?, ?, ?)",
        (user_id, symbol, when_at, note),
    )


def delete_earning(conn, user_id: int, earning_id: int) -> None:
    conn.execute("DELETE FROM earnings WHERE user_id = ? AND id = ?", (user_id, earning_id))


def news_events(conn) -> list[dict]:
    return many(conn, "SELECT * FROM news_events ORDER BY when_utc, impact, title")


def sample_count(conn, user_id: int, note: str) -> int:
    row = one(conn, "SELECT COUNT(*) AS n FROM trades WHERE user_id = ? AND notes = ?", (user_id, note))
    return int(row["n"] if row else 0)


def store_media(conn, user_id: int, filename: str, content: bytes) -> None:
    conn.execute("INSERT INTO media_blobs (user_id, filename, content) VALUES (?, ?, ?)", (user_id, filename, content))


def media_content(conn, user_id: int, filename: str) -> bytes | None:
    row = one(conn, "SELECT content FROM media_blobs WHERE user_id = ? AND filename = ?", (user_id, filename))
    return bytes(row["content"]) if row else None


def delete_media(conn, user_id: int, filename: str) -> None:
    conn.execute("DELETE FROM media_blobs WHERE user_id = ? AND filename = ?", (user_id, filename))
