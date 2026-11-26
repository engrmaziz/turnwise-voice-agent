"""SQLite calendar. Writes use BEGIN IMMEDIATE and an idempotency key."""

from __future__ import annotations

import contextlib
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path

SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


class CalendarError(Exception):
    """Typed calendar failure. Disk full and schema errors use this class."""


@dataclass(frozen=True, slots=True)
class CalendarResult:
    ok: bool
    appointment_id: str = ""
    slot_id: str = ""
    version: int = 0
    conflict: bool = False
    alternatives: tuple[str, ...] = ()
    error: str = ""


def migrate(path: Path, roster: tuple[str, ...]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise CalendarError("open failed") from exc
    try:
        conn = sqlite3.connect(str(path), timeout=5.0)
    except sqlite3.Error as exc:
        raise CalendarError("open failed") from exc
    try:
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        for name in roster:
            conn.execute(
                "INSERT OR IGNORE INTO doctors(id, name) VALUES (?, ?)",
                (name, name),
            )
        conn.commit()
    except sqlite3.Error as exc:
        raise CalendarError("migrate failed") from exc
    finally:
        conn.close()


def seed_slot(
    path: Path, *, doctor_id: str, start_iso: str, slot_id: str, version: int = 1
) -> None:
    conn = _open(path)
    try:
        conn.execute(
            "INSERT OR REPLACE INTO slots(id, doctor_id, start_iso, version, taken) "
            "VALUES (?, ?, ?, ?, 0)",
            (slot_id, doctor_id, start_iso, version),
        )
        conn.commit()
    except sqlite3.Error as exc:
        raise CalendarError("seed failed") from exc
    finally:
        conn.close()


def bump_version(path: Path, slot_id: str) -> int:
    conn = _open(path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT version FROM slots WHERE id = ?", (slot_id,)).fetchone()
        if row is None:
            conn.execute("ROLLBACK")
            raise CalendarError("missing slot")
        version = int(row[0]) + 1
        conn.execute("UPDATE slots SET version = ? WHERE id = ?", (version, slot_id))
        conn.commit()
        return version
    except sqlite3.Error as exc:
        raise CalendarError("bump failed") from exc
    finally:
        conn.close()


def execute_book(
    path: Path,
    *,
    key: str,
    patient_name: str,
    phone: str,
    doctor_id: str,
    start_iso: str,
    offered_slot_id: str,
    offered_version: int,
    slots_json: dict[str, str],
) -> CalendarResult:
    """Insert one appointment. A second call with the same key returns the first row."""
    conn = _open(path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        existing = conn.execute(
            "SELECT appointment_id FROM idempotency WHERE key = ?", (key,)
        ).fetchone()
        if existing is not None:
            conn.execute("COMMIT")
            return CalendarResult(ok=True, appointment_id=str(existing[0]))
        slot = conn.execute(
            "SELECT id, version, taken FROM slots WHERE id = ?",
            (offered_slot_id,),
        ).fetchone()
        if slot is None:
            alts = _alternatives(conn, doctor_id, start_iso)
            conn.execute("ROLLBACK")
            return CalendarResult(ok=False, conflict=True, alternatives=alts)
        slot_id, version, taken = str(slot[0]), int(slot[1]), int(slot[2])
        if taken != 0 or version != offered_version:
            alts = _alternatives(conn, doctor_id, start_iso)
            conn.execute("ROLLBACK")
            return CalendarResult(ok=False, conflict=True, alternatives=alts)
        changed = conn.execute(
            "UPDATE slots SET taken = 1, version = version + 1 "
            "WHERE id = ? AND version = ? AND taken = 0",
            (slot_id, offered_version),
        )
        if changed.rowcount != 1:
            alts = _alternatives(conn, doctor_id, start_iso)
            conn.execute("ROLLBACK")
            return CalendarResult(ok=False, conflict=True, alternatives=alts)
        patient_id = _upsert_patient(conn, patient_name, phone)
        appt_id = _next_appt_id(conn)
        conn.execute(
            "INSERT INTO appointments(id, patient_id, doctor_id, start_iso, status, slots_json) "
            "VALUES (?, ?, ?, ?, 'booked', ?)",
            (appt_id, patient_id, doctor_id, start_iso, json.dumps(slots_json)),
        )
        conn.execute(
            "INSERT INTO idempotency(key, appointment_id) VALUES (?, ?)",
            (key, appt_id),
        )
        conn.commit()
        return CalendarResult(ok=True, appointment_id=appt_id)
    except sqlite3.Error as exc:
        with contextlib.suppress(sqlite3.Error):
            conn.execute("ROLLBACK")
        raise CalendarError("write failed") from exc
    finally:
        conn.close()


def offer_slot(path: Path, *, doctor_id: str, start_iso: str) -> CalendarResult:
    """Read-only offer. Writes nothing except the connection."""
    conn = _open(path)
    try:
        row = conn.execute(
            "SELECT id, version FROM slots WHERE doctor_id = ? AND start_iso = ? AND taken = 0",
            (doctor_id, start_iso),
        ).fetchone()
        if row is None:
            alts = _alternatives(conn, doctor_id, start_iso)
            return CalendarResult(ok=False, conflict=True, alternatives=alts)
        return CalendarResult(ok=True, slot_id=str(row[0]), version=int(row[1]))
    except sqlite3.Error as exc:
        raise CalendarError("offer failed") from exc
    finally:
        conn.close()


def appointment_count(path: Path) -> int:
    conn = _open(path)
    try:
        row = conn.execute("SELECT COUNT(*) FROM appointments").fetchone()
        return int(row[0]) if row else 0
    finally:
        conn.close()


def load_appointment(path: Path, appointment_id: str) -> dict[str, str]:
    conn = _open(path)
    try:
        row = conn.execute(
            "SELECT id, doctor_id, start_iso, status, slots_json FROM appointments WHERE id = ?",
            (appointment_id,),
        ).fetchone()
        if row is None:
            raise CalendarError("missing appointment")
        return {
            "id": str(row[0]),
            "doctor_id": str(row[1]),
            "start_iso": str(row[2]),
            "status": str(row[3]),
            "slots_json": str(row[4]),
        }
    finally:
        conn.close()


def _open(path: Path) -> sqlite3.Connection:
    try:
        conn = sqlite3.connect(str(path), timeout=5.0)
    except sqlite3.Error as exc:
        raise CalendarError("open failed") from exc
    return conn


def _upsert_patient(conn: sqlite3.Connection, name: str, phone: str) -> str:
    row = conn.execute(
        "SELECT id FROM patients WHERE name = ? AND phone = ?", (name, phone)
    ).fetchone()
    if row is not None:
        return str(row[0])
    patient_id = f"P{conn.execute('SELECT COUNT(*) FROM patients').fetchone()[0] + 1:04d}"
    conn.execute(
        "INSERT INTO patients(id, name, phone, dob) VALUES (?, ?, ?, '')",
        (patient_id, name, phone),
    )
    return patient_id


def _next_appt_id(conn: sqlite3.Connection) -> str:
    n = conn.execute("SELECT COUNT(*) FROM appointments").fetchone()[0]
    return f"A{int(n) + 1:04d}"


def _alternatives(conn: sqlite3.Connection, doctor_id: str, start_iso: str) -> tuple[str, ...]:
    rows = conn.execute(
        "SELECT start_iso FROM slots WHERE doctor_id = ? AND taken = 0 AND start_iso != ? "
        "ORDER BY start_iso LIMIT 3",
        (doctor_id, start_iso),
    ).fetchall()
    return tuple(str(item[0]) for item in rows)
