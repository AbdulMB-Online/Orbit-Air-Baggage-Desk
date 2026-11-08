"""ORB-52 / ORB-56: acceptance tests written before implementation.

Tests-only scope: do not add application implementations or make commits.
Proposed public API (not prescribed by the lab):
    db.connect_db(path) -> sqlite3.Connection
    db.init_db(connection) -> None
    claims.file_claim(connection, *, passenger, flight, claim_type, tier,
                      now, actor, note="") -> integer claim ID
    claims.list_claims(connection, *, status=None, tier=None) -> mappings
Validation errors must be ValueError (or a subclass); storage failures propagate.
Transaction contract for review: standalone filing commits the claim/history
pair; filing inside an active caller transaction must not commit that transaction.
Batch callers explicitly begin their transaction before the first filing; merely
entering a sqlite3 connection context does not start a transaction. The caller
then commits or rolls back the entire batch, including all history entries.
Function names, return shapes, and exception types remain project API choices,
not assignment-mandated names. Tests below preserve those proposed choices.
Application imports happen inside calls so every case can collect before the
modules exist. No stubs, mocks, skips, or expected-failure markers are used.
"""

import importlib
import sqlite3
from contextlib import closing
from datetime import UTC, datetime, timedelta, timezone

import pytest

FILED_AT = datetime(2026, 11, 2, 14, 0, tzinfo=UTC)


@pytest.fixture
def database_factory(tmp_path):
    connections = []

    def open_database():
        db = importlib.import_module("db")
        connection = db.connect_db(tmp_path / "claims.sqlite3")
        connections.append(connection)
        db.init_db(connection)
        return connection

    yield open_database
    for connection in connections:
        connection.close()


@pytest.fixture
def file_claim():
    def file_with_defaults(connection, **overrides):
        values = {
            "passenger": "Avery Quinn",
            "flight": "OA123",
            "claim_type": "delayed",
            "tier": "standard",
            "now": FILED_AT,
            "actor": "desk.agent",
        }
        values.update(overrides)
        return importlib.import_module("claims").file_claim(connection, **values)

    return file_with_defaults


def _rows(connection, query, parameters=()):
    with closing(connection.execute(query, parameters)) as cursor:
        names = [column[0] for column in cursor.description]
        return [dict(zip(names, row, strict=True)) for row in cursor.fetchall()]


def _snapshot(connection):
    return {
        "claims": _rows(connection, "SELECT * FROM claims ORDER BY id"),
        "history": _rows(connection, "SELECT * FROM history ORDER BY id"),
    }


def _timestamp(value):
    parsed = datetime.fromisoformat(value)
    assert parsed.utcoffset() == timedelta(0), "Stored timestamps must be UTC"
    return parsed


def _insert_claim_row(connection, **overrides):
    """Bypass business rules only to exercise actual database constraints."""
    values = {
        "passenger": "Schema Fixture",
        "flight": "OA456",
        "type": "lost",
        "tier": "standard",
        "status": "open",
        "assigned_agent": None,
        "note": "",
        "filed_at": FILED_AT.isoformat(),
        "deadline": (FILED_AT + timedelta(hours=72)).isoformat(),
    }
    values.update(overrides)
    with closing(connection.execute(
        "INSERT INTO claims "
        "(passenger, flight, type, tier, status, assigned_agent, note, "
        "filed_at, deadline) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        tuple(values.values()),
    )) as cursor:
        return cursor.lastrowid


def _insert_history_row(connection, claim_id, **overrides):
    """Insert fixture data directly to test storage rather than filing logic."""
    values = {
        "claim_id": claim_id,
        "old_status": None,
        "new_status": "open",
        "actor": "schema.agent",
        "changed_at": FILED_AT.isoformat(),
    }
    values.update(overrides)
    with closing(connection.execute(
        "INSERT INTO history "
        "(claim_id, old_status, new_status, actor, changed_at) "
        "VALUES (?, ?, ?, ?, ?)",
        tuple(values.values()),
    )) as cursor:
        return cursor.lastrowid


def _seed_existing_claim(connection):
    claim_id = _insert_claim_row(connection, note="Preserve this existing note")
    _insert_history_row(connection, claim_id)
    connection.commit()
    return claim_id


def test_schema_contains_required_tables_and_columns(database_factory):
    connection = database_factory()
    required = {
        "claims": {
            "id", "passenger", "flight", "type", "tier", "status",
            "assigned_agent", "note", "filed_at", "deadline",
        },
        "history": {
            "id", "claim_id", "old_status", "new_status", "actor", "changed_at",
        },
    }
    for table, columns in required.items():
        metadata = {
            column["name"]: column
            for column in _rows(connection, f"PRAGMA table_info({table})")
        }
        assert columns <= metadata.keys()
        assert metadata["id"]["type"].upper() == "INTEGER"
        assert metadata["id"]["pk"] == 1
        for name in columns - {"id"}:
            expected_type = "INTEGER" if name == "claim_id" else "TEXT"
            assert metadata[name]["type"].upper() == expected_type
            if name not in {"assigned_agent", "old_status"}:
                assert metadata[name]["notnull"] == 1


def test_schema_initialization_preserves_existing_claims(database_factory):
    connection = database_factory()
    claim_id = _seed_existing_claim(connection)
    connection.execute(
        "UPDATE claims SET status = ?, assigned_agent = ? WHERE id = ?",
        ("assigned", "fixture.agent", claim_id),
    )
    _insert_history_row(
        connection, claim_id, old_status="open", new_status="assigned",
        actor="fixture.agent", changed_at=(FILED_AT + timedelta(hours=1)).isoformat(),
    )
    connection.commit()
    before = _snapshot(connection)
    assert len(before["history"]) == 2

    importlib.import_module("db").init_db(connection)

    assert connection.execute("SELECT id FROM claims").fetchall()[0][0] == claim_id
    assert connection.execute("SELECT COUNT(*) FROM claims").fetchone()[0] == 1
    assert _snapshot(connection) == before


def test_history_foreign_key_rejects_a_missing_claim(database_factory):
    connection = database_factory()
    assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1

    with pytest.raises(sqlite3.IntegrityError, match="(?i)foreign key"):
        connection.execute(
            "INSERT INTO history "
            "(claim_id, old_status, new_status, actor, changed_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (99999, None, "open", "desk.agent", FILED_AT.isoformat()),
        )


@pytest.mark.parametrize(
    ("column", "value"),
    [("type", "missing"), ("tier", "platinum"), ("status", "pending")],
)
def test_sqlite_check_constraints_reject_unknown_values(
    database_factory, column, value,
):
    connection = database_factory()

    with pytest.raises(sqlite3.IntegrityError, match="(?i)check"):
        _insert_claim_row(connection, **{column: value})

    assert connection.execute("SELECT COUNT(*) FROM claims").fetchone()[0] == 0


@pytest.mark.parametrize(
    "column",
    ["passenger", "flight", "type", "tier", "status", "note", "filed_at", "deadline"],
)
def test_sqlite_rejects_null_required_claim_values(database_factory, column):
    connection = database_factory()

    with pytest.raises(sqlite3.IntegrityError, match="(?i)not null"):
        _insert_claim_row(connection, **{column: None})

    assert connection.execute("SELECT COUNT(*) FROM claims").fetchone()[0] == 0


@pytest.mark.parametrize("column", ["claim_id", "new_status", "actor", "changed_at"])
def test_sqlite_rejects_null_required_history_values(database_factory, column):
    connection = database_factory()
    claim_id = _seed_existing_claim(connection)
    before = _snapshot(connection)

    values = {"claim_id": claim_id, column: None}
    with pytest.raises(sqlite3.IntegrityError, match="(?i)not null"):
        _insert_history_row(connection, **values)

    assert _snapshot(connection) == before


@pytest.mark.parametrize("column", ["passenger", "flight", "assigned_agent"])
@pytest.mark.parametrize("value", ["", " \t\n "])
def test_sqlite_rejects_blank_claim_text(database_factory, column, value):
    connection = database_factory()

    with pytest.raises(sqlite3.IntegrityError, match="(?i)check"):
        _insert_claim_row(connection, **{column: value})

    assert connection.execute("SELECT COUNT(*) FROM claims").fetchone()[0] == 0


@pytest.mark.parametrize("actor", ["", " \t\n "])
def test_sqlite_rejects_blank_history_actor(database_factory, actor):
    connection = database_factory()
    claim_id = _seed_existing_claim(connection)
    before = _snapshot(connection)

    with pytest.raises(sqlite3.IntegrityError, match="(?i)check"):
        _insert_history_row(connection, claim_id, actor=actor)

    assert _snapshot(connection) == before


@pytest.mark.parametrize("column", ["old_status", "new_status"])
def test_sqlite_rejects_unknown_history_status(database_factory, column):
    connection = database_factory()
    claim_id = _seed_existing_claim(connection)
    before = _snapshot(connection)

    with pytest.raises(sqlite3.IntegrityError, match="(?i)check"):
        _insert_history_row(connection, claim_id, **{column: "pending"})

    assert _snapshot(connection) == before


def test_sqlite_defaults_allow_unassigned_claim_and_initial_history(database_factory):
    connection = database_factory()
    with closing(connection.execute(
        "INSERT INTO claims (passenger, flight, type, tier, filed_at, deadline) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (
            "Default Values", "OA987", "damaged", "gold", FILED_AT.isoformat(),
            (FILED_AT + timedelta(hours=4)).isoformat(),
        ),
    )) as cursor:
        claim_id = cursor.lastrowid
    history_id = _insert_history_row(connection, claim_id)

    claim = _rows(connection, "SELECT * FROM claims WHERE id = ?", (claim_id,))[0]
    assert claim["status"] == "open"
    assert claim["note"] == ""
    assert claim["assigned_agent"] is None
    history = _rows(connection, "SELECT * FROM history WHERE id = ?", (history_id,))[0]
    assert history["old_status"] is None
    assert history["new_status"] == "open"


def test_filing_persists_a_complete_open_claim_and_initial_history(
    database_factory, file_claim,
):
    connection = database_factory()

    claim_id = file_claim(connection)

    assert isinstance(claim_id, int)
    claim = _rows(connection, "SELECT * FROM claims WHERE id = ?", (claim_id,))[0]
    assert claim["passenger"] == "Avery Quinn"
    assert claim["flight"] == "OA123"
    assert claim["type"] == "delayed"
    assert claim["tier"] == "standard"
    assert claim["status"] == "open"
    assert claim["assigned_agent"] is None
    assert claim["note"] == ""
    assert _timestamp(claim["filed_at"]) == FILED_AT
    assert _timestamp(claim["deadline"]) == FILED_AT + timedelta(hours=72)
    history = _rows(
        connection, "SELECT * FROM history WHERE claim_id = ?", (claim_id,),
    )
    assert len(history) == 1
    assert history[0]["old_status"] is None
    assert history[0]["new_status"] == "open"
    assert history[0]["actor"] == "desk.agent"
    assert _timestamp(history[0]["changed_at"]) == FILED_AT


@pytest.mark.parametrize(
    ("overrides", "field"),
    [
        ({"passenger": ""}, "passenger"),
        ({"passenger": " \t "}, "passenger"),
        ({"flight": ""}, "flight"),
        ({"flight": " \t "}, "flight"),
        ({"claim_type": "missing"}, "type"),
        ({"tier": "platinum"}, "tier"),
    ],
)
@pytest.mark.parametrize("existing_record", [False, True], ids=["empty", "populated"])
def test_invalid_filing_is_clear_and_has_no_side_effects(
    database_factory, file_claim, overrides, field, existing_record,
):
    connection = database_factory()
    if existing_record:
        _seed_existing_claim(connection)
    before = _snapshot(connection)

    with pytest.raises(ValueError, match=f"(?i){field}"):
        file_claim(connection, **overrides)

    assert _snapshot(connection) == before
    assert connection.execute("SELECT COUNT(*) FROM claims").fetchone()[0] == int(
        existing_record,
    )
    assert connection.execute("SELECT COUNT(*) FROM history").fetchone()[0] == int(
        existing_record,
    )


@pytest.mark.parametrize("tier,hours", [("gold", 4), ("silver", 24), ("standard", 72)])
def test_deadline_is_based_on_the_injected_filing_time(
    database_factory, file_claim, tier, hours,
):
    connection = database_factory()
    claim_id = file_claim(connection, tier=tier)

    claim = _rows(connection, "SELECT * FROM claims WHERE id = ?", (claim_id,))[0]

    assert _timestamp(claim["filed_at"]) == FILED_AT
    assert _timestamp(claim["deadline"]) == FILED_AT + timedelta(hours=hours)


@pytest.mark.parametrize(
    "now",
    [
        FILED_AT.astimezone(timezone(timedelta(hours=-5))),
        FILED_AT.replace(tzinfo=None),
    ],
    ids=["offset-normalized", "naive-means-utc"],
)
def test_filing_normalizes_timestamps_to_utc(database_factory, file_claim, now):
    connection = database_factory()
    claim_id = file_claim(connection, now=now, tier="gold")

    claim = _rows(connection, "SELECT * FROM claims WHERE id = ?", (claim_id,))[0]

    assert _timestamp(claim["filed_at"]) == FILED_AT
    assert _timestamp(claim["deadline"]) == FILED_AT + timedelta(hours=4)
    history = _rows(connection, "SELECT * FROM history WHERE claim_id = ?", (claim_id,))
    assert _timestamp(history[0]["changed_at"]) == FILED_AT


def test_notes_are_stored_as_literal_data(database_factory, file_claim):
    connection = database_factory()
    note = "O'Brien's bag '); DROP TABLE claims; -- 🧳"

    claim_id = file_claim(connection, note=note)

    assert connection.execute(
        "SELECT note FROM claims WHERE id = ?", (claim_id,),
    ).fetchone()[0] == note
    assert connection.execute("SELECT COUNT(*) FROM claims").fetchone()[0] == 1


def test_filing_is_visible_to_an_independent_connection(
    database_factory, file_claim, tmp_path,
):
    connection = database_factory()
    claim_id = file_claim(connection)

    with closing(sqlite3.connect(tmp_path / "claims.sqlite3")) as observer:
        assert observer.execute("SELECT id FROM claims").fetchone()[0] == claim_id
        assert observer.execute("SELECT claim_id FROM history").fetchone()[0] == claim_id


def test_caller_can_roll_back_multiple_filings_together(
    database_factory, file_claim, tmp_path,
):
    connection = database_factory()
    _seed_existing_claim(connection)
    before = _snapshot(connection)

    with connection:
        connection.execute("BEGIN")
        first_id = file_claim(connection, passenger="First Batch Passenger")
        second_id = file_claim(connection, passenger="Second Batch Passenger")
        assert first_id != second_id
        assert connection.in_transaction, "Filing must not commit the caller's batch"
        assert len(_snapshot(connection)["claims"]) == len(before["claims"]) + 2
        assert len(_snapshot(connection)["history"]) == len(before["history"]) + 2
        with closing(sqlite3.connect(tmp_path / "claims.sqlite3")) as observer:
            assert _snapshot(observer) == before
        connection.rollback()

    assert _snapshot(connection) == before
    with closing(sqlite3.connect(tmp_path / "claims.sqlite3")) as observer:
        assert _snapshot(observer) == before


def test_caller_commit_persists_the_entire_filing_batch(
    database_factory, file_claim, tmp_path,
):
    connection = database_factory()
    _seed_existing_claim(connection)
    before = _snapshot(connection)

    with connection:
        connection.execute("BEGIN")
        first_id = file_claim(connection, passenger="First Batch Passenger")
        second_id = file_claim(connection, passenger="Second Batch Passenger")
        assert first_id != second_id
        assert connection.in_transaction, "Filing must leave the caller in control"
        expected = _snapshot(connection)
        assert len(expected["claims"]) == len(before["claims"]) + 2
        assert len(expected["history"]) == len(before["history"]) + 2
        with closing(sqlite3.connect(tmp_path / "claims.sqlite3")) as observer:
            assert _snapshot(observer) == before

    assert _snapshot(connection) == expected
    with closing(sqlite3.connect(tmp_path / "claims.sqlite3")) as observer:
        assert _snapshot(observer) == expected


def test_history_failure_rolls_back_every_filing_in_the_callers_batch(
    database_factory, file_claim, tmp_path,
):
    connection = database_factory()
    _seed_existing_claim(connection)
    before = _snapshot(connection)
    connection.execute(
        "CREATE TRIGGER block_second_batch_history BEFORE INSERT ON history "
        "WHEN NEW.claim_id IN "
        "(SELECT id FROM claims WHERE passenger = 'Failing Batch Passenger') "
        "BEGIN SELECT RAISE(ABORT, 'batch history write blocked'); END"
    )
    connection.commit()

    with (
        pytest.raises(sqlite3.IntegrityError, match="batch history write blocked"),
        connection,
    ):
        connection.execute("BEGIN")
        file_claim(connection, passenger="First Batch Passenger")
        assert connection.in_transaction
        assert len(_snapshot(connection)["claims"]) == len(before["claims"]) + 1
        assert len(_snapshot(connection)["history"]) == len(before["history"]) + 1
        file_claim(connection, passenger="Failing Batch Passenger")

    assert _snapshot(connection) == before
    with closing(sqlite3.connect(tmp_path / "claims.sqlite3")) as observer:
        assert _snapshot(observer) == before


def test_listing_an_empty_database_returns_no_claims(database_factory):
    connection = database_factory()

    assert list(importlib.import_module("claims").list_claims(connection)) == []


@pytest.mark.parametrize(
    ("filters", "expected"),
    [
        ({}, {"gold-open", "silver-assigned", "gold-resolved", "standard-open"}),
        ({"status": "open"}, {"gold-open", "standard-open"}),
        ({"status": "assigned"}, {"silver-assigned"}),
        ({"status": "resolved"}, {"gold-resolved"}),
        ({"tier": "gold"}, {"gold-open", "gold-resolved"}),
        ({"tier": "silver"}, {"silver-assigned"}),
        ({"tier": "standard"}, {"standard-open"}),
        ({"status": "open", "tier": "gold"}, {"gold-open"}),
        ({"status": "assigned", "tier": "standard"}, set()),
        ({"status": "closed"}, set()),
    ],
)
def test_listing_filters_use_intersection(
    database_factory, filters, expected,
):
    connection = database_factory()
    samples = [
        ("gold-open", "gold", "open", "delayed"),
        ("silver-assigned", "silver", "assigned", "lost"),
        ("gold-resolved", "gold", "resolved", "damaged"),
        ("standard-open", "standard", "open", "delayed"),
    ]
    ids = {}
    for label, tier, status, claim_type in samples:
        # SQL fixture data isolates listing from the unimplemented filing API.
        ids[label] = _insert_claim_row(
            connection, passenger=label, tier=tier, type=claim_type, status=status,
            assigned_agent="fixture.agent" if status != "open" else None,
        )
    connection.commit()

    claims = list(importlib.import_module("claims").list_claims(connection, **filters))

    assert {claim["id"] for claim in claims} == {ids[label] for label in expected}
    assert len(claims) == len(expected), "Listing must not contain duplicate claims"


@pytest.mark.parametrize("status", ["escalated", "closed"])
def test_listing_returns_existing_claims_for_other_valid_statuses(
    database_factory, status,
):
    connection = database_factory()
    claim_id = _insert_claim_row(
        connection, status=status, assigned_agent="fixture.agent",
    )
    _insert_claim_row(connection, passenger="Unrelated Open Claim")
    connection.commit()

    claims = list(importlib.import_module("claims").list_claims(
        connection, status=status,
    ))

    assert {claim["id"] for claim in claims} == {claim_id}
    assert len(claims) == 1


@pytest.mark.parametrize(
    ("filters", "field"),
    [
        ({"status": "pending"}, "status"),
        ({"tier": "platinum"}, "tier"),
        ({"status": "open", "tier": "platinum"}, "tier"),
    ],
)
def test_listing_rejects_invalid_filters(database_factory, filters, field):
    connection = database_factory()
    _seed_existing_claim(connection)
    before = _snapshot(connection)

    with pytest.raises(ValueError, match=f"(?i){field}"):
        importlib.import_module("claims").list_claims(connection, **filters)

    assert _snapshot(connection) == before


def test_history_failure_rolls_back_filing_and_preserves_existing_records(
    database_factory, file_claim, tmp_path,
):
    connection = database_factory()
    existing_id = file_claim(connection)
    before_claims = _rows(connection, "SELECT * FROM claims ORDER BY id")
    before_history = _rows(connection, "SELECT * FROM history ORDER BY id")
    connection.execute(
        "CREATE TRIGGER block_history BEFORE INSERT ON history "
        "BEGIN SELECT RAISE(ABORT, 'history write blocked'); END"
    )
    connection.commit()

    with pytest.raises(sqlite3.IntegrityError, match="history write blocked"):
        file_claim(connection, passenger="New Passenger")

    assert _rows(connection, "SELECT * FROM claims ORDER BY id") == before_claims
    assert _rows(connection, "SELECT * FROM history ORDER BY id") == before_history
    with closing(sqlite3.connect(tmp_path / "claims.sqlite3")) as observer:
        assert observer.execute("SELECT id FROM claims").fetchall() == [(existing_id,)]
        assert observer.execute("SELECT COUNT(*) FROM history").fetchone()[0] == 1
