"""Claim rules and history; every time value comes from the caller."""

import csv
import sqlite3
from contextlib import closing
from datetime import UTC, datetime, timedelta

from db import CLAIM_TYPES, STATUSES, TIERS, atomic

DEADLINE_HOURS = {"gold": 4, "silver": 24, "standard": 72}
ALLOWED_TRANSITIONS = {
    "open": ("assigned", "escalated"),
    "assigned": ("resolved", "escalated"),
    "escalated": ("assigned", "resolved"),
    "resolved": ("closed",),
    "closed": (),
}
SEED_COLUMNS = ["passenger", "flight", "type", "tier", "note"]


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


def is_overdue(deadline: datetime, *, now: datetime) -> bool:
    """Compare injected times strictly, interpreting naive inputs as UTC."""
    return _utc(now) > _utc(deadline)


def _validate_filing_fields(
    passenger: str, flight: str, claim_type: str, tier: str, *, actor: str, note: str,
) -> None:
    _required_text(passenger, "passenger")
    _required_text(flight, "flight")
    _required_text(actor, "actor")
    _enum_value(claim_type, CLAIM_TYPES, "type")
    _enum_value(tier, TIERS, "tier")
    if not isinstance(note, str):
        raise TypeError("note must be text")


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
    _validate_filing_fields(
        passenger, flight, claim_type, tier, actor=actor, note=note,
    )
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


# STRETCH GOAL 2
def claim_report(connection: sqlite3.Connection, *, now: datetime) -> list[dict]:
    """Count open claims and overdue unresolved claims by tier without writes."""
    current_time = _utc(now)
    totals = {tier: {"tier": tier, "open": 0, "overdue": 0} for tier in TIERS}
    with closing(connection.execute(
        "SELECT tier, status, deadline FROM claims WHERE status IN (?, ?, ?)",
        ("open", "assigned", "escalated"),
    )) as cursor:
        for claim in cursor:
            counts = totals[claim["tier"]]
            if claim["status"] == "open":
                counts["open"] += 1
            if is_overdue(datetime.fromisoformat(claim["deadline"]), now=current_time):
                counts["overdue"] += 1
    return list(totals.values())


def _get_claim(connection: sqlite3.Connection, claim_id: int) -> sqlite3.Row:
    with closing(connection.execute(
        "SELECT * FROM claims WHERE id = ?", (claim_id,),
    )) as cursor:
        claim = cursor.fetchone()
    if claim is None:
        raise ValueError(f"Claim {claim_id} not found")
    return claim


def _change_status(
    connection: sqlite3.Connection,
    claim_id: int,
    new_status: str,
    *,
    now: datetime,
    actor: str,
    agent: str | None = None,
) -> None:
    """Apply a checked status change with its history in one savepoint."""
    actor = _required_text(actor, "actor")
    changed_at = _utc(now).isoformat()
    with atomic(connection):
        claim = _get_claim(connection, claim_id)
        old_status = claim["status"]
        if new_status not in ALLOWED_TRANSITIONS[old_status]:
            raise ValueError(
                f"Cannot change claim {claim_id} from {old_status} to {new_status}",
            )
        assigned_agent = agent if new_status == "assigned" else claim["assigned_agent"]
        connection.execute(
            "UPDATE claims SET status = ?, assigned_agent = ? WHERE id = ?",
            (new_status, assigned_agent, claim_id),
        )
        connection.execute(
            "INSERT INTO history "
            "(claim_id, old_status, new_status, actor, changed_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (claim_id, old_status, new_status, actor, changed_at),
        )


def assign_claim(
    connection: sqlite3.Connection,
    claim_id: int,
    *,
    agent: str,
    now: datetime,
    actor: str,
) -> None:
    """Assign an open or escalated claim to a nonblank agent."""
    agent = _required_text(agent, "agent")
    _change_status(connection, claim_id, "assigned", now=now, actor=actor, agent=agent)


def resolve_claim(
    connection: sqlite3.Connection,
    claim_id: int,
    *,
    now: datetime,
    actor: str,
) -> None:
    """Resolve an assigned or escalated claim, preserving its owner."""
    _change_status(connection, claim_id, "resolved", now=now, actor=actor)


def close_claim(
    connection: sqlite3.Connection,
    claim_id: int,
    *,
    now: datetime,
    actor: str,
) -> None:
    """Close a resolved claim; a closed claim cannot transition again."""
    _change_status(connection, claim_id, "closed", now=now, actor=actor)


def get_history(connection: sqlite3.Connection, claim_id: int) -> list[dict]:
    """Return one existing claim's complete history in entry-ID order."""
    _get_claim(connection, claim_id)
    with closing(connection.execute(
        "SELECT * FROM history WHERE claim_id = ? ORDER BY id", (claim_id,),
    )) as cursor:
        return [dict(row) for row in cursor.fetchall()]


def escalate_overdue(connection: sqlite3.Connection, *, now: datetime) -> list[int]:
    """Escalate eligible claims atomically without committing a caller transaction."""
    current_time = _utc(now)
    escalated_ids = []
    with atomic(connection):
        with closing(connection.execute(
            "SELECT id, deadline FROM claims WHERE status IN (?, ?) ORDER BY id",
            ("open", "assigned"),
        )) as cursor:
            candidates = cursor.fetchall()
        for claim in candidates:
            deadline = datetime.fromisoformat(claim["deadline"])
            if is_overdue(deadline, now=current_time):
                _change_status(
                    connection, claim["id"], "escalated",
                    now=current_time, actor="system",
                )
                escalated_ids.append(claim["id"])
    return escalated_ids


def seed_claims(
    connection: sqlite3.Connection,
    reader: csv.DictReader,
    *,
    now: datetime,
    actor: str,
) -> list[int]:
    """Validate every CSV row before importing claims/history as one atomic batch."""
    actor = _required_text(actor, "actor")
    filed_at = _utc(now)
    if reader.fieldnames != SEED_COLUMNS:
        raise ValueError(f"CSV columns must be exactly: {','.join(SEED_COLUMNS)}")
    validated_rows = []
    try:
        for row in reader:
            try:
                if None in row or any(value is None for value in row.values()):
                    raise ValueError("expected exactly five columns")
                _validate_filing_fields(
                    row["passenger"], row["flight"], row["type"], row["tier"],
                    actor=actor, note=row["note"],
                )
            except (ValueError, TypeError) as error:
                raise ValueError(f"CSV row {reader.line_num}: {error}") from error
            validated_rows.append(row)
    except csv.Error as error:
        raise ValueError(f"CSV row {reader.line_num}: {error}") from error

    claim_ids = []
    with atomic(connection):
        for row in validated_rows:
            claim_ids.append(file_claim(
                connection, passenger=row["passenger"], flight=row["flight"],
                claim_type=row["type"], tier=row["tier"], note=row["note"],
                now=filed_at, actor=actor,
            ))
    return claim_ids
