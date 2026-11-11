"""Report counts are read-only, tier-specific, and use the supplied clock."""

import re
import sqlite3
import subprocess
import sys
from contextlib import closing
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest

import claims
import db

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 11, 2, 18, tzinfo=UTC)


@pytest.fixture
def database(tmp_path):
    with closing(db.connect_db(tmp_path / "claims.sqlite3")) as connection:
        db.init_db(connection)
        yield connection


def _insert(connection, tier, status, deadline):
    with connection:
        cursor = connection.execute(
            "INSERT INTO claims (passenger, flight, type, tier, status, filed_at, deadline) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("Report fixture", "OA101", "delayed", tier, status,
             (NOW - timedelta(days=4)).isoformat(), deadline.isoformat()),
        )
        connection.execute(
            "INSERT INTO history (claim_id, old_status, new_status, actor, changed_at) "
            "VALUES (?, NULL, ?, ?, ?)",
            (cursor.lastrowid, status, "fixture", NOW.isoformat()),
        )
        cursor.close()


def _snapshot(connection):
    return {
        table: [tuple(row) for row in connection.execute(f"SELECT * FROM {table} ORDER BY id")]
        for table in ("claims", "history")
    }


def _counts(rows):
    assert len(rows) == 3
    assert {row["tier"] for row in rows} == {"standard", "silver", "gold"}
    return {row["tier"]: (row["open"], row["overdue"]) for row in rows}


def test_empty_report_includes_zero_counts_for_every_tier(database):
    assert _counts(claims.claim_report(database, now=NOW)) == {
        "standard": (0, 0), "silver": (0, 0), "gold": (0, 0),
    }
    assert _snapshot(database) == {"claims": [], "history": []}


def test_report_counts_all_unresolved_overdue_claims_strictly_and_without_writes(database):
    past, future = NOW - timedelta(minutes=1), NOW + timedelta(minutes=1)
    equal_with_offset = NOW.astimezone(timezone(timedelta(hours=5, minutes=30)))
    for status, deadline in (
        ("open", past), ("open", equal_with_offset), ("open", future),
        ("assigned", past), ("escalated", past), ("resolved", past), ("closed", past),
    ):
        _insert(database, "standard", status, deadline)
    _insert(database, "silver", "open", past)
    _insert(database, "silver", "assigned", future)
    _insert(database, "gold", "assigned", past)
    _insert(database, "gold", "escalated", past)
    before = _snapshot(database)
    writes = database.total_changes

    assert _counts(claims.claim_report(database, now=NOW)) == {
        "standard": (3, 3), "silver": (1, 1), "gold": (0, 2),
    }
    assert _snapshot(database) == before
    assert database.total_changes == writes


def test_cli_report_uses_now_for_boundary_counts_and_preserves_records(database, tmp_path):
    _insert(database, "gold", "open", NOW)
    _insert(database, "silver", "closed", NOW - timedelta(days=1))
    before = _snapshot(database)
    for clock, overdue in ((NOW, 0), (NOW + timedelta(minutes=1), 1)):
        result = subprocess.run(
            [sys.executable, str(ROOT / "main.py"), "--now", clock.isoformat(), "report"],
            cwd=tmp_path, capture_output=True, text=True, timeout=10, check=False,
        )
        assert result.returncode == 0, result.stderr
        rows = re.findall(r"tier='(standard|silver|gold)' \| open=(\d+) \| overdue=(\d+)",
                          result.stdout)
        assert len(rows) == 3, result.stdout
        assert {tier: (int(opened), int(late)) for tier, opened, late in rows} == {
            "standard": (0, 0), "silver": (0, 0), "gold": (1, overdue),
        }
    assert _snapshot(database) == before
    with closing(sqlite3.connect(tmp_path / "claims.sqlite3")) as observer:
        assert _snapshot(observer) == before
