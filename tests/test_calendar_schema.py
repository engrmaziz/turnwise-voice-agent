"""Migrate creates the calendar tables on a temp file."""

import sqlite3
from pathlib import Path

import pytest

from tools.calendar import CalendarError, migrate


def test_migrate_creates_tables(tmp_path: Path) -> None:
    db = tmp_path / "clinic.sqlite"
    migrate(db, ("Dr. Avery Lang",))
    conn = sqlite3.connect(str(db))
    try:
        names = {
            str(row[0])
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
    finally:
        conn.close()
    assert {
        "patients",
        "doctors",
        "slots",
        "appointments",
        "idempotency",
    } <= names
    conn = sqlite3.connect(str(db))
    try:
        doctor = conn.execute("SELECT id FROM doctors WHERE id = ?", ("Dr. Avery Lang",)).fetchone()
    finally:
        conn.close()
    assert doctor is not None


def test_parent_is_file_is_typed_calendar_error(tmp_path: Path) -> None:
    blocked = tmp_path / "not_a_dir"
    blocked.write_text("x", encoding="utf-8")
    with pytest.raises(CalendarError):
        migrate(blocked / "clinic.sqlite", ("Dr. Avery Lang",))
