"""Assignment/status/history acceptance tests, written before implementation.

Proposed public API (function names are not prescribed by the assignment):
    claims.assign_claim(connection, claim_id, *, agent, now, actor)
    claims.resolve_claim(connection, claim_id, *, now, actor)
    claims.close_claim(connection, claim_id, *, now, actor)
    claims.get_history(connection, claim_id) -> ordered history mappings
Mutator return values are deliberately unspecified. Rejected transitions and
missing IDs raise clear ValueErrors; SQLite write failures propagate. Each
mutation commits standalone, or joins an explicitly begun caller transaction
without committing it, consistent with the existing filing API.

Fixtures insert known database states directly, without depending on another
status operation or the future escalator. APIs are looked up inside tests so
the tests collect while those functions are absent. No mocks, skips, xfails,
existing-test changes, application code, branches, or commits are needed.
"""

import sqlite3
from contextlib import closing
from datetime import UTC, datetime, timedelta, timezone

import pytest

import claims
import db

FILED_AT = datetime(2026, 11, 2, 14, 0, tzinfo=UTC)
CHANGED_AT = FILED_AT + timedelta(hours=1)
ACTOR = "desk.o'neil"
NEW_AGENT = "Casey O'Neil"
OPERATIONS = (
    ("assign_claim", "open", "assigned"),
    ("resolve_claim", "assigned", "resolved"),
    ("close_claim", "resolved", "closed"),
)


@pytest.fixture
def database(tmp_path):
    with closing(db.connect_db(tmp_path / "status.sqlite3")) as connection:
        db.init_db(connection)
        yield connection


@pytest.fixture
def make_claim(database):
    def insert(status="open"):
        # Static, legal fixture paths; no production transition logic is used.
        paths = {
            "open": (),
            "assigned": ("assigned",),
            "escalated": ("assigned", "escalated"),
            "resolved": ("assigned", "resolved"),
            "closed": ("assigned", "resolved", "closed"),
        }
        with database, closing(database.execute(
            "INSERT INTO claims "
            "(passenger, flight, type, tier, status, assigned_agent, note, "
            "filed_at, deadline) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "Morgan Rivera", "OA456", "damaged", "silver", status,
                None if status == "open" else "previous.agent",
                "Keep this passenger's note unchanged",
                FILED_AT.isoformat(),
                (FILED_AT + timedelta(hours=24)).isoformat(),
            ),
        )) as cursor:
            claim_id = cursor.lastrowid
            _insert_history(database, claim_id, None, "open", "filing.agent", FILED_AT)
            old_status = "open"
            for minute, new_status in enumerate(paths[status], start=1):
                actor = "system" if new_status == "escalated" else "fixture.agent"
                _insert_history(
                    database, claim_id, old_status, new_status, actor,
                    FILED_AT + timedelta(minutes=minute),
                )
                old_status = new_status
        return claim_id

    return insert


def _insert_history(connection, claim_id, old_status, new_status, actor, when):
    with closing(connection.execute(
        "INSERT INTO history "
        "(claim_id, old_status, new_status, actor, changed_at) VALUES (?, ?, ?, ?, ?)",
        (claim_id, old_status, new_status, actor, when.isoformat()),
    )):
        pass


def _rows(connection, query, parameters=()):
    with closing(connection.execute(query, parameters)) as cursor:
        return [dict(row) for row in cursor.fetchall()]


def _snapshot(connection):
    return {
        "claims": _rows(connection, "SELECT * FROM claims ORDER BY id"),
        "history": _rows(connection, "SELECT * FROM history ORDER BY id"),
    }


def _claim(connection, claim_id):
    rows = _rows(connection, "SELECT * FROM claims WHERE id = ?", (claim_id,))
    assert len(rows) == 1
    return rows[0]


def _assert_utc_timestamp(value, expected):
    parsed = datetime.fromisoformat(value)
    assert parsed.utcoffset() == timedelta(0), "History timestamps must be UTC"
    assert parsed == expected


def _change(operation, connection, claim_id, *, now=CHANGED_AT, actor=ACTOR,
            agent=NEW_AGENT):
    arguments = {"now": now, "actor": actor}
    if operation == "assign_claim":
        arguments["agent"] = agent
    return getattr(claims, operation)(connection, claim_id, **arguments)


def _assert_change(connection, before, claim_id, source, destination, *, agent):
    expected_claims = [
        row | {"status": destination, "assigned_agent": agent}
        if row["id"] == claim_id else row
        for row in before["claims"]
    ]
    assert _rows(connection, "SELECT * FROM claims ORDER BY id") == expected_claims
    history = _rows(connection, "SELECT * FROM history ORDER BY id")
    assert len(history) == len(before["history"]) + 1
    assert history[:-1] == before["history"]
    entry = history[-1]
    assert entry["id"] > before["history"][-1]["id"]
    assert {
        key: value for key, value in entry.items()
        if key not in {"id", "changed_at"}
    } == {
        "claim_id": claim_id,
        "old_status": source,
        "new_status": destination,
        "actor": ACTOR,
    }
    _assert_utc_timestamp(entry["changed_at"], CHANGED_AT)


@pytest.mark.parametrize("source", ["open", "escalated"])
def test_assign_saves_ownership_and_one_complete_history_entry(
    database, make_claim, tmp_path, source,
):
    claim_id = make_claim(source)
    make_claim("closed")
    before = _snapshot(database)

    _change("assign_claim", database, claim_id)

    _assert_change(database, before, claim_id, source, "assigned", agent=NEW_AGENT)
    with closing(db.connect_db(tmp_path / "status.sqlite3")) as observer:
        assert _snapshot(observer) == _snapshot(database)


@pytest.mark.parametrize("source", ["assigned", "escalated"])
def test_resolve_preserves_owner_and_other_fields_with_complete_history(
    database, make_claim, tmp_path, source,
):
    claim_id = make_claim(source)
    make_claim("open")
    before = _snapshot(database)

    _change("resolve_claim", database, claim_id)

    _assert_change(
        database, before, claim_id, source, "resolved", agent="previous.agent",
    )
    with closing(db.connect_db(tmp_path / "status.sqlite3")) as observer:
        assert _snapshot(observer) == _snapshot(database)


def test_close_preserves_owner_and_other_fields_with_complete_history(
    database, make_claim, tmp_path,
):
    claim_id = make_claim("resolved")
    make_claim("open")
    before = _snapshot(database)

    _change("close_claim", database, claim_id)

    _assert_change(
        database, before, claim_id, "resolved", "closed", agent="previous.agent",
    )
    with closing(db.connect_db(tmp_path / "status.sqlite3")) as observer:
        assert _snapshot(observer) == _snapshot(database)


@pytest.mark.parametrize(
    ("operation", "source", "destination"),
    [
        ("assign_claim", "assigned", "assigned"),
        ("assign_claim", "resolved", "assigned"),
        ("assign_claim", "closed", "assigned"),
        ("resolve_claim", "open", "resolved"),
        ("resolve_claim", "resolved", "resolved"),
        ("resolve_claim", "closed", "resolved"),
        ("close_claim", "open", "closed"),
        ("close_claim", "assigned", "closed"),
        ("close_claim", "escalated", "closed"),
        ("close_claim", "closed", "closed"),
    ],
)
def test_forbidden_changes_are_clear_and_leave_all_records_unchanged(
    database, make_claim, operation, source, destination,
):
    claim_id = make_claim(source)
    make_claim("open")
    before = _snapshot(database)

    with pytest.raises(ValueError) as error:
        _change(operation, database, claim_id)

    message = str(error.value).lower()
    assert source in message
    assert destination in message
    assert _snapshot(database) == before


@pytest.mark.parametrize("source", ["open", "escalated"])
@pytest.mark.parametrize("agent", ["", " \t\n "])
def test_blank_agents_are_rejected_without_changing_claims_or_history(
    database, make_claim, source, agent,
):
    claim_id = make_claim(source)
    before = _snapshot(database)

    with pytest.raises(ValueError, match="(?i)agent"):
        _change("assign_claim", database, claim_id, agent=agent)

    assert _snapshot(database) == before


@pytest.mark.parametrize("operation", [
    "assign_claim", "resolve_claim", "close_claim", "get_history",
])
def test_missing_claim_ids_are_reported_without_writes(database, make_claim, operation):
    existing_id = make_claim("assigned")
    missing_id = existing_id + 1000
    before = _snapshot(database)

    missing_message = "(?i)(not found|no such|does not exist|unknown|missing)"
    with pytest.raises(ValueError, match=missing_message) as error:
        if operation == "get_history":
            claims.get_history(database, missing_id)
        else:
            _change(operation, database, missing_id)

    assert str(missing_id) in str(error.value)
    assert _snapshot(database) == before


@pytest.mark.parametrize(("operation", "source", "destination"), OPERATIONS)
@pytest.mark.parametrize("actor", ["", " \t\n "])
def test_blank_actors_are_rejected_before_writes(
    database, make_claim, operation, source, destination, actor,
):
    claim_id = make_claim(source)
    before = _snapshot(database)

    with pytest.raises(ValueError, match="(?i)actor"):
        _change(operation, database, claim_id, actor=actor)

    assert _snapshot(database) == before


@pytest.mark.parametrize(("operation", "source", "destination"), OPERATIONS)
@pytest.mark.parametrize("now", [
    CHANGED_AT.astimezone(timezone(timedelta(hours=5, minutes=30))),
    CHANGED_AT.replace(tzinfo=None),
], ids=["offset-normalized", "naive-means-utc"])
def test_status_history_uses_the_injected_time_normalized_to_utc(
    database, make_claim, operation, source, destination, now,
):
    claim_id = make_claim(source)
    before = _snapshot(database)

    _change(operation, database, claim_id, now=now)

    _assert_change(
        database, before, claim_id, source, destination,
        agent=NEW_AGENT if operation == "assign_claim" else "previous.agent",
    )


def test_lifecycle_appends_history_including_initial_filing(database, make_claim):
    claim_id = make_claim()
    original = _claim(database, claim_id)
    expected = [(None, "open", "filing.agent", FILED_AT)]
    for minute, (operation, source, destination) in enumerate(OPERATIONS, start=1):
        now = CHANGED_AT + timedelta(minutes=minute)
        actor = f"manual.actor.{minute}"
        _change(operation, database, claim_id, now=now, actor=actor)
        expected.append((source, destination, actor, now))

    entries = claims.get_history(database, claim_id)
    assert len(entries) == 4
    assert [dict(entry) for entry in entries] == _rows(
        database, "SELECT * FROM history WHERE claim_id = ? ORDER BY id", (claim_id,),
    )
    assert [
        (entry["old_status"], entry["new_status"], entry["actor"])
        for entry in entries
    ] == [(old, new, actor) for old, new, actor, when in expected]
    for entry, (_, _, _, when) in zip(entries, expected, strict=True):
        _assert_utc_timestamp(entry["changed_at"], when)
    assert _claim(database, claim_id) == original | {
        "status": "closed", "assigned_agent": NEW_AGENT,
    }


def test_history_is_read_only_complete_and_filtered_in_entry_id_order(
    database, make_claim,
):
    claim_id = make_claim()
    make_claim("resolved")  # Interleave another claim's history IDs.
    with database:
        # An injected clock can move backwards or repeat; entry ID defines order.
        _insert_history(database, claim_id, "open", "assigned", "first.actor",
                        FILED_AT + timedelta(minutes=30))
        _insert_history(database, claim_id, "assigned", "resolved", "second.actor",
                        FILED_AT + timedelta(minutes=10))
        _insert_history(database, claim_id, "resolved", "closed", "third.actor",
                        FILED_AT + timedelta(minutes=10))
        database.execute(
            "UPDATE claims SET status = ?, assigned_agent = ? WHERE id = ?",
            ("closed", "fixture.agent", claim_id),
        )
    before = _snapshot(database)
    expected = [row for row in before["history"] if row["claim_id"] == claim_id]

    entries = claims.get_history(database, claim_id)

    assert len(entries) == 4
    assert [dict(entry) for entry in entries] == expected
    assert [dict(entry) for entry in claims.get_history(database, claim_id)] == expected
    assert _snapshot(database) == before


@pytest.mark.parametrize(("operation", "source", "destination"), OPERATIONS)
def test_failed_history_write_rolls_back_status_and_ownership(
    database, make_claim, tmp_path, operation, source, destination,
):
    claim_id = make_claim(source)
    make_claim("closed")
    # The trigger identifier and integer ID are test-owned, never user input.
    database.execute(f"""
        CREATE TEMP TRIGGER reject_status_history BEFORE INSERT ON history
        WHEN NEW.claim_id = {claim_id}
        BEGIN
            SELECT RAISE(ABORT, 'forced history failure');
        END
    """)
    before = _snapshot(database)

    with pytest.raises(sqlite3.IntegrityError, match="forced history failure"):
        _change(operation, database, claim_id)

    assert _snapshot(database) == before
    assert not database.in_transaction
    with closing(db.connect_db(tmp_path / "status.sqlite3")) as observer:
        assert _snapshot(observer) == before


@pytest.mark.parametrize(("operation", "source", "destination"), OPERATIONS)
def test_caller_can_roll_back_status_and_history_together(
    database, make_claim, tmp_path, operation, source, destination,
):
    claim_id = make_claim(source)
    before = _snapshot(database)
    database.execute("BEGIN")

    _change(operation, database, claim_id)

    assert database.in_transaction
    _assert_change(
        database, before, claim_id, source, destination,
        agent=NEW_AGENT if operation == "assign_claim" else "previous.agent",
    )
    with closing(db.connect_db(tmp_path / "status.sqlite3")) as observer:
        assert _snapshot(observer) == before
    database.rollback()
    assert _snapshot(database) == before


@pytest.mark.parametrize(("operation", "source", "destination"), OPERATIONS)
def test_caller_commit_persists_status_and_its_history(
    database, make_claim, tmp_path, operation, source, destination,
):
    claim_id = make_claim(source)
    before = _snapshot(database)
    database.execute("BEGIN")

    _change(operation, database, claim_id)
    database.commit()

    with closing(db.connect_db(tmp_path / "status.sqlite3")) as observer:
        _assert_change(
            observer, before, claim_id, source, destination,
            agent=NEW_AGENT if operation == "assign_claim" else "previous.agent",
        )
