"""PostgreSQL connection using the journal's parameterized SQL interface."""

import re
import sqlite3

import psycopg
from psycopg.rows import dict_row


def parameters(sql: str) -> str:
    """Convert the journal's fixed qmark/named placeholders, never their values."""
    return re.sub(r"(?<!:):([a-z_]+)", r"%(\1)s", sql.replace("?", "%s"))


class PostgresConnection:
    def __init__(self, url: str):
        self.raw = psycopg.connect(url, row_factory=dict_row, connect_timeout=10)
        # Keep service operations inside one atomic transaction; nested transaction
        # blocks below are savepoints, including for duplicate account names.
        self.raw.execute("BEGIN")

    def execute(self, sql, args=()):
        if sql.lstrip().lower().startswith("insert into accounts"):
            # Onboarding can skip an existing account without aborting the rest
            # of its transaction, matching the local journal's behavior.
            try:
                with self.raw.transaction():
                    return self.raw.execute(parameters(sql), args or None)
            except psycopg.IntegrityError as exc:
                raise sqlite3.IntegrityError("Account constraints were not satisfied.") from exc
        return self.raw.execute(parameters(sql), args or None)

    def executemany(self, sql, rows):
        return self.raw.cursor().executemany(parameters(sql), rows)

    def executescript(self, sql):
        return self.raw.execute(sql)

    def transaction(self):
        return self.raw.transaction()

    def commit(self):
        self.raw.commit()

    def rollback(self):
        self.raw.rollback()

    def close(self):
        self.raw.close()
