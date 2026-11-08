"""Claim rules and history; every time value comes from the caller."""

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
