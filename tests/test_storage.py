import os
import sqlite3
import unittest
from unittest.mock import patch
from uuid import uuid4

from app import db


class StorageTests(unittest.TestCase):
    def test_production_requires_a_managed_database(self):
        with patch.dict(os.environ, {"DATABASE_URL": "", "OMENSITE_REQUIRE_DATABASE": "1"}):
            with self.assertRaisesRegex(RuntimeError, "Attach a managed PostgreSQL"):
                db.connect()
        with patch.dict(os.environ, {"DATABASE_URL": "mysql://unsupported"}):
            with self.assertRaisesRegex(RuntimeError, "PostgreSQL connection URL"):
                db.connect()

    def test_schema_media_and_transaction_persistence(self):
        email = uuid4().hex + "@storage.example.com"
        with db.session() as conn:
            db.init_db(conn)
            db.init_db(conn)
            user_id = db.create_user(conn, email, "fixture", "fixture", "America/New_York")
            db.insert_account(conn, user_id, "Personal", "personal", 0, None, None, None)
            with self.assertRaises(sqlite3.IntegrityError):
                db.insert_account(conn, user_id, "Personal", "personal", 0, None, None, None)
            # A duplicate account must not abort the surrounding transaction.
            db.store_media(conn, user_id, "fixture.png", b"persistent chart bytes")
        with db.session() as conn:
            self.assertEqual(db.media_content(conn, user_id, "fixture.png"), b"persistent chart bytes")
            self.assertIsNone(db.media_content(conn, user_id + 100000, "fixture.png"))
        with self.assertRaisesRegex(RuntimeError, "rollback fixture"):
            with db.session() as conn:
                conn.execute("UPDATE users SET display_name = ? WHERE id = ?", ("Uncommitted", user_id))
                db.delete_media(conn, user_id, "fixture.png")
                raise RuntimeError("rollback fixture")
        with db.session() as conn:
            self.assertIsNone(db.user_by_id(conn, user_id)["display_name"])
            self.assertEqual(db.media_content(conn, user_id, "fixture.png"), b"persistent chart bytes")
