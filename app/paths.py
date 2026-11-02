"""Where the journal keeps its database and chart images."""

from __future__ import annotations

import os
from pathlib import Path

from app.services_error import JournalError


def data_dir() -> Path:
    override = os.environ.get("OMENSITE_DATA")
    root = Path(override) if override else Path(__file__).resolve().parent.parent / "data"
    root.mkdir(parents=True, exist_ok=True)
    return root


def db_path() -> Path:
    return data_dir() / "journal.sqlite3"


def ensure_upload_dir(user_id: int) -> Path:
    path = data_dir() / "uploads" / str(int(user_id))
    path.mkdir(parents=True, exist_ok=True)
    return path


def import_dir(user_id: int) -> Path:
    path = data_dir() / "imports" / str(int(user_id))
    path.mkdir(parents=True, exist_ok=True)
    return path


def upload_path(user_id: int, filename: str) -> Path:
    if not filename or Path(filename).name != filename or filename in {".", ".."}:
        raise JournalError("File not found.")
    root = (data_dir() / "uploads" / str(int(user_id))).resolve()
    path = (root / filename).resolve()
    if not path.is_relative_to(root):
        raise JournalError("File not found.")
    return path
