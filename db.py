"""SQLite connections, schema, and composable transaction boundaries."""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

CLAIM_TYPES = ("delayed", "lost", "damaged")
TIERS = ("standard", "silver", "gold")
STATUSES = ("open", "assigned", "escalated", "resolved", "closed")

# SQLite's default trim removes only spaces. Include the whitespace characters
# recognized by Python's str.strip so direct SQL cannot insert blank text either.
_WHITESPACE = "char(9,10,11,12,13,28,29,30,31,32,133,160,5760,8192,8193,8194,8195,8196,8197,8198,8199,8200,8201,8202,8232,8233,8239,8287,12288)"

_CLAIMS_SCHEMA = f"""
CREATE TABLE IF NOT EXISTS claims (
    id INTEGER PRIMARY KEY,
    passenger TEXT NOT NULL CHECK(length(trim(passenger, {_WHITESPACE})) > 0),
    flight TEXT NOT NULL CHECK(length(trim(flight, {_WHITESPACE})) > 0),
    type TEXT NOT NULL CHECK(type IN ('delayed', 'lost', 'damaged')),
    tier TEXT NOT NULL CHECK(tier IN ('standard', 'silver', 'gold')),
    status TEXT NOT NULL DEFAULT 'open'
        CHECK(status IN ('open', 'assigned', 'escalated', 'resolved', 'closed')),
    assigned_agent TEXT CHECK(
        assigned_agent IS NULL OR length(trim(assigned_agent, {_WHITESPACE})) > 0
    ),
    note TEXT NOT NULL DEFAULT '',
    filed_at TEXT NOT NULL,
    deadline TEXT NOT NULL
)
"""

_HISTORY_SCHEMA = f"""
CREATE TABLE IF NOT EXISTS history (
    id INTEGER PRIMARY KEY,
    claim_id INTEGER NOT NULL REFERENCES claims(id),
    old_status TEXT CHECK(
        old_status IS NULL OR
        old_status IN ('open', 'assigned', 'escalated', 'resolved', 'closed')
    ),
    new_status TEXT NOT NULL
        CHECK(new_status IN ('open', 'assigned', 'escalated', 'resolved', 'closed')),
    actor TEXT NOT NULL CHECK(length(trim(actor, {_WHITESPACE})) > 0),
    changed_at TEXT NOT NULL
)
"""


def connect_db(path: str | Path) -> sqlite3.Connection:
    """Open a mapping-row connection with foreign keys and explicit BEGIN support."""
    connection = sqlite3.connect(
        path, autocommit=sqlite3.LEGACY_TRANSACTION_CONTROL,
    )
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("PRAGMA foreign_keys = ON")
    except BaseException:
        connection.close()
        raise
    return connection


@contextmanager
def atomic(connection: sqlite3.Connection) -> Iterator[None]:
    """Commit a standalone write or join an outer transaction without committing it."""
    # Identifiers cannot be bound as SQL parameters. This name is generated here,
    # never taken from passenger input, and stays unique across nested operations.
    savepoint = f"orbit_{uuid4().hex}"
    connection.execute(f"SAVEPOINT {savepoint}")
    try:
        yield
        connection.execute(f"RELEASE SAVEPOINT {savepoint}")
    except BaseException:
        # A SQLite RAISE(ROLLBACK) can already have ended the transaction.
        if connection.in_transaction:
            connection.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
            connection.execute(f"RELEASE SAVEPOINT {savepoint}")
        raise


def init_db(connection: sqlite3.Connection) -> None:
    """Create both tables atomically without replacing existing records."""
    with atomic(connection):
        connection.execute(_CLAIMS_SCHEMA)
        connection.execute(_HISTORY_SCHEMA)
