"""Claim filing and listing rules; every time value comes from the caller."""

import sqlite3
from contextlib import closing
from datetime import UTC, datetime, timedelta

from db import CLAIM_TYPES, STATUSES, TIERS, atomic

DEADLINE_HOURS = {"gold": 4, "silver": 24, "standard": 72}


def _required_text(value: str, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must not be blank")
    return value


def _enum_value(value: str, allowed: tuple[str, ...], field: str) -> str:
    if not isinstance(value, str) or value not in allowed:
        raise ValueError(f"Invalid {field}; expected one of: {', '.join(allowed)}")
    return value


def _utc(value: datetime) -> datetime:
    if not isinstance(value, datetime):
        raise TypeError("now must be a datetime")
    if value.utcoffset() is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def file_claim(
    connection: sqlite3.Connection,
    *,
    passenger: str,
    flight: str,
    claim_type: str,
    tier: str,
    now: datetime,
    actor: str,
    note: str = "",
) -> int:
    """File a claim and its initial history as one composable atomic operation."""
    passenger = _required_text(passenger, "passenger")
    flight = _required_text(flight, "flight")
    actor = _required_text(actor, "actor")
    claim_type = _enum_value(claim_type, CLAIM_TYPES, "type")
    tier = _enum_value(tier, TIERS, "tier")
    if not isinstance(note, str):
        raise TypeError("note must be text")
    filed_at = _utc(now)
    deadline = filed_at + timedelta(hours=DEADLINE_HOURS[tier])

    with atomic(connection):
        with closing(connection.execute(
            "INSERT INTO claims "
            "(passenger, flight, type, tier, note, filed_at, deadline) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                passenger, flight, claim_type, tier, note,
                filed_at.isoformat(), deadline.isoformat(),
            ),
        )) as cursor:
            claim_id = int(cursor.lastrowid)
        connection.execute(
            "INSERT INTO history "
            "(claim_id, old_status, new_status, actor, changed_at) "
            "VALUES (?, NULL, 'open', ?, ?)",
            (claim_id, actor, filed_at.isoformat()),
        )
    return claim_id


def list_claims(
    connection: sqlite3.Connection,
    *,
    status: str | None = None,
    tier: str | None = None,
) -> list[dict]:
    """List each matching claim once, combining filters with AND."""
    conditions = []
    parameters = []
    if status is not None:
        conditions.append("status = ?")
        parameters.append(_enum_value(status, STATUSES, "status"))
    if tier is not None:
        conditions.append("tier = ?")
        parameters.append(_enum_value(tier, TIERS, "tier"))

    query = "SELECT * FROM claims"
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY id"
    with closing(connection.execute(query, parameters)) as cursor:
        return [dict(row) for row in cursor.fetchall()]
