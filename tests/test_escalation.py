"""Six focused tests for overdue evaluation and atomic batch escalation.

Proposed API (Python names/signatures are project choices, not lab mandates):
    claims.is_overdue(deadline: datetime, *, now: datetime) -> bool
    claims.escalate_overdue(connection, *, now: datetime) -> list[int]
Normalize datetime inputs to UTC; naive values mean UTC. Escalation supplies
the system actor internally and preserves ownership. A standalone call commits
the entire batch with its history; a call inside an explicitly begun caller
transaction must leave that transaction under caller control. Returned ID order
is unspecified. Storage errors propagate.
Fixtures use direct SQL so setup does not depend on another business operation.
No parametrization: six functions collect exactly six cases. Missing APIs are
looked up during execution so every test can collect before implementation.
"""

import sqlite3
from contextlib import closing
from datetime import UTC, datetime, timedelta, timezone

import pytest

import claims
import db

NOW = datetime(2026, 11, 2, 14, 0, tzinfo=UTC)
MINUTE = timedelta(minutes=1)


@pytest.fixture
def database(tmp_path):
    with closing(db.connect_db(tmp_path / "escalation.sqlite3")) as connection:
        db.init_db(connection)
        yield connection


@pytest.fixture
def make_claim(database):
    def insert(status="open", *, deadline=NOW - MINUTE):
        paths = {
            "open": (),
            "assigned": ("assigned",),
            "escalated": ("assigned", "escalated"),
            "resolved": ("assigned", "resolved"),
            "closed": ("assigned", "resolved", "closed"),
        }
        filed_at = deadline - timedelta(hours=4)
        with database, closing(database.execute(
            "INSERT INTO claims "
            "(passenger, flight, type, tier, status, assigned_agent, note, "
            "filed_at, deadline) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "Jordan Ellis", "OA789", "lost", "gold", status,
                None if status == "open" else "existing.agent",
                "Preserve this claim's details", filed_at.isoformat(),
                deadline.isoformat(),
            ),
        )) as cursor:
            claim_id = cursor.lastrowid
            history = [(claim_id, None, "open", "filing.agent", filed_at.isoformat())]
            old_status = "open"
            for minute, new_status in enumerate(paths[status], start=1):
                changed_at = (
                    deadline + timedelta(seconds=30)
                    if new_status == "escalated" else filed_at + minute * MINUTE
                )
                history.append((
                    claim_id, old_status, new_status,
                    "system" if new_status == "escalated" else "fixture.agent",
                    changed_at.isoformat(),
                ))
                old_status = new_status
            with closing(database.executemany(
                "INSERT INTO history "
                "(claim_id, old_status, new_status, actor, changed_at) "
                "VALUES (?, ?, ?, ?, ?)", history,
            )):
                pass
        return claim_id

    return insert


def _rows(connection, query):
    with closing(connection.execute(query)) as cursor:
        return [dict(row) for row in cursor.fetchall()]


def _snapshot(connection):
    return {
        "claims": _rows(connection, "SELECT * FROM claims ORDER BY id"),
        "history": _rows(connection, "SELECT * FROM history ORDER BY id"),
    }


def test_overdue_is_strict_at_deadline_boundaries_and_uses_utc():
    assert claims.is_overdue(NOW, now=NOW - MINUTE) is False
    assert claims.is_overdue(NOW, now=NOW) is False
    assert claims.is_overdue(NOW, now=NOW + MINUTE) is True
    offset = timezone(timedelta(hours=5, minutes=30))
    assert claims.is_overdue(NOW, now=NOW.astimezone(offset)) is False
    assert claims.is_overdue(
        NOW.replace(tzinfo=None), now=(NOW + MINUTE).astimezone(offset),
    ) is True
    assert claims.is_overdue(NOW, now=NOW.replace(tzinfo=None)) is False


def test_escalation_selects_only_eligible_claims_and_reports_their_ids(
    database, make_claim, tmp_path,
):
    eligible = [make_claim("open"), make_claim("assigned")]
    for status in ("escalated", "resolved", "closed"):
        make_claim(status)
    for status in ("open", "assigned"):
        make_claim(status, deadline=NOW)
        make_claim(status, deadline=NOW + MINUTE)
    before = _snapshot(database)

    escalated_ids = claims.escalate_overdue(database, now=NOW)

    assert sorted(escalated_ids) == eligible  # Also catches duplicates.
    after = _snapshot(database)
    assert after["claims"] == [
        row | {"status": "escalated"} if row["id"] in eligible else row
        for row in before["claims"]
    ]
    previous_count = len(before["history"])
    assert after["history"][:previous_count] == before["history"]
    assert sorted(
        row["claim_id"] for row in after["history"][previous_count:]
    ) == eligible
    with closing(db.connect_db(tmp_path / "escalation.sqlite3")) as observer:
        assert _snapshot(observer) == after


def test_escalation_appends_complete_system_history_with_injected_utc_time(
    database, make_claim, tmp_path,
):
    open_id = make_claim("open")
    assigned_id = make_claim("assigned")
    original = _snapshot(database)
    before = original["history"]
    offset_now = NOW.astimezone(timezone(timedelta(hours=-5)))
    database.execute("BEGIN")

    claims.escalate_overdue(database, now=offset_now)

    assert database.in_transaction, "Escalation must not commit the caller's transaction"
    history = _snapshot(database)["history"]
    assert history[:len(before)] == before
    entries = sorted(history[len(before):], key=lambda row: row["claim_id"])
    assert len(entries) == 2
    for entry, claim_id, source in zip(
        entries, (open_id, assigned_id), ("open", "assigned"), strict=True,
    ):
        assert {key: value for key, value in entry.items()
                if key not in {"id", "changed_at"}} == {
            "claim_id": claim_id,
            "old_status": source,
            "new_status": "escalated",
            "actor": "system",
        }
        timestamp = datetime.fromisoformat(entry["changed_at"])
        assert timestamp.utcoffset() == timedelta(0)
        assert timestamp == NOW

    assert _snapshot(database)["claims"] == [
        row | {"status": "escalated"} for row in original["claims"]
    ]
    with closing(db.connect_db(tmp_path / "escalation.sqlite3")) as observer:
        assert _snapshot(observer) == original
        database.rollback()
        assert _snapshot(database) == original
        assert _snapshot(observer) == original


def test_empty_escalation_batch_returns_no_ids_and_makes_no_writes(database):
    before = _snapshot(database)

    assert claims.escalate_overdue(database, now=NOW) == []

    assert _snapshot(database) == before


def test_repeated_escalation_is_a_noop_without_duplicate_history(database, make_claim):
    eligible = [make_claim("open"), make_claim("assigned")]
    before = _snapshot(database)
    assert sorted(claims.escalate_overdue(database, now=NOW)) == eligible
    after_first = _snapshot(database)
    assert all(row["status"] == "escalated" for row in after_first["claims"])
    assert len(after_first["history"]) == len(before["history"]) + 2

    assert claims.escalate_overdue(database, now=NOW + timedelta(hours=1)) == []

    assert _snapshot(database) == after_first


def test_second_history_failure_rolls_back_the_entire_batch(
    database, make_claim, tmp_path,
):
    first_id = make_claim("open")
    second_id = make_claim("assigned")
    make_claim("closed")
    # Fixture-owned integer IDs make the trigger independent of processing order.
    # Fail only after one eligible claim's escalation history was already written.
    database.execute(f"""
        CREATE TEMP TRIGGER reject_second_escalation_history
        BEFORE INSERT ON history
        WHEN NEW.new_status = 'escalated' AND EXISTS (
            SELECT 1 FROM history WHERE new_status = 'escalated'
            AND claim_id IN ({first_id}, {second_id})
        )
        BEGIN
            SELECT RAISE(ABORT, 'forced escalation history failure');
        END
    """)
    before = _snapshot(database)

    with pytest.raises(sqlite3.IntegrityError, match="forced escalation history failure"):
        claims.escalate_overdue(database, now=NOW)

    assert _snapshot(database) == before
    assert not database.in_transaction
    with closing(db.connect_db(tmp_path / "escalation.sqlite3")) as observer:
        assert _snapshot(observer) == before
