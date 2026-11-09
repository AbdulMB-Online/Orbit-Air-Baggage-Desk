"""Command parsing, invocation time, file handling, and readable CLI results."""

import argparse
import csv
import sqlite3
import sys
from contextlib import closing
from datetime import UTC, datetime
from getpass import getuser
from pathlib import Path

import claims
from db import CLAIM_TYPES, STATUSES, TIERS, connect_db, init_db


def _iso_time(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("--now must be an ISO timestamp") from error
    if parsed.utcoffset() is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Orbit Air Baggage Desk")
    parser.add_argument("--now", type=_iso_time, metavar="ISO_TIME",
                        help="use this time instead of the current time; precedes the command")
    commands = parser.add_subparsers(dest="command", required=True)
    filing = commands.add_parser("file", help="file a baggage claim")
    filing.add_argument("--passenger", required=True)
    filing.add_argument("--flight", required=True)
    filing.add_argument("--type", dest="claim_type", choices=CLAIM_TYPES, required=True)
    filing.add_argument("--tier", choices=TIERS, required=True)
    filing.add_argument("--note", default="")
    listing = commands.add_parser("list", help="list claims with optional filters")
    listing.add_argument("--status", choices=STATUSES)
    listing.add_argument("--tier", choices=TIERS)
    assignment = commands.add_parser("assign", help="assign an open or escalated claim")
    assignment.add_argument("claim_id", type=int)
    assignment.add_argument("--agent", required=True)
    for name, help_text in (
        ("resolve", "resolve an assigned or escalated claim"),
        ("close", "close a resolved claim"),
        ("history", "show one claim's complete history"),
    ):
        command = commands.add_parser(name, help=help_text)
        command.add_argument("claim_id", type=int)
    commands.add_parser("escalate", help="escalate all overdue open or assigned claims")
    seed = commands.add_parser("seed", help="import claims from a CSV file atomically")
    seed.add_argument("csv_path", type=Path)
    return parser


def _print_rows(rows: list[dict]) -> None:
    if not rows:
        print("No records found.")
    for row in rows:
        # repr keeps free-text newlines/control characters inside a displayed value.
        print(" | ".join(f"{key}={value!r}" for key, value in row.items()))


def _dispatch(args: argparse.Namespace, connection: sqlite3.Connection,
              now: datetime, actor: str) -> None:
    if args.command == "file":
        claim_id = claims.file_claim(
            connection, passenger=args.passenger, flight=args.flight,
            claim_type=args.claim_type, tier=args.tier, note=args.note,
            now=now, actor=actor,
        )
        print(f"Filed claim {claim_id}.")
    elif args.command == "list":
        _print_rows(claims.list_claims(connection, status=args.status, tier=args.tier))
    elif args.command == "assign":
        claims.assign_claim(connection, args.claim_id, agent=args.agent, now=now, actor=actor)
        print(f"Assigned claim {args.claim_id} to {args.agent!r}.")
    elif args.command == "resolve":
        claims.resolve_claim(connection, args.claim_id, now=now, actor=actor)
        print(f"Resolved claim {args.claim_id}.")
    elif args.command == "close":
        claims.close_claim(connection, args.claim_id, now=now, actor=actor)
        print(f"Closed claim {args.claim_id}.")
    elif args.command == "escalate":
        claim_ids = claims.escalate_overdue(connection, now=now)
        if claim_ids:
            print("Escalated claim IDs: " + ", ".join(map(str, claim_ids)))
        else:
            print("No overdue claims to escalate.")
    elif args.command == "history":
        _print_rows(claims.get_history(connection, args.claim_id))
    elif args.command == "seed":
        with args.csv_path.open(encoding="utf-8", newline="") as stream:
            reader = csv.DictReader(stream, strict=True)
            claim_ids = claims.seed_claims(connection, reader, now=now, actor=actor)
        print(f"Seeded {len(claim_ids)} claims. IDs: {', '.join(map(str, claim_ids))}")


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    now = args.now if args.now is not None else datetime.now(UTC)
    try:
        actor = getuser()
        with closing(connect_db("claims.sqlite3")) as connection:
            init_db(connection)
            _dispatch(args, connection, now, actor)
    except (ValueError, OSError, sqlite3.Error, csv.Error) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
