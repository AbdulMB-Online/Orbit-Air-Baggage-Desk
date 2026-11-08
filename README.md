# Orbit Air Baggage Desk

## Overview

Orbit Air Baggage Desk manages baggage claims in SQLite. The Python API supports filing, deadlines, filtered listing, assignment, resolution, closure, and audit history. Automatic escalation, CSV import, and `main.py` belong to the remaining required branches.

## Installation and Setup

Requires Python 3.12 or newer. From the repository root:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
```

The application uses the Python standard library; `requirements-dev.txt` supplies pinned pytest and Ruff versions. Keep local SQLite databases, their journal/WAL files, virtual environments, and `.env` out of Git.

## Usage

Until the CLI branch adds `python main.py`, use the Python API:

```python
from contextlib import closing
from datetime import datetime
from getpass import getuser

from claims import file_claim, list_claims
from db import connect_db, init_db

with closing(connect_db("claims.sqlite3")) as connection:
    init_db(connection)
    claim_id = file_claim(
        connection,
        passenger="Avery Quinn",
        flight="OA123",
        claim_type="delayed",
        tier="gold",
        now=datetime.fromisoformat("2026-11-02T14:00:00+00:00"),
        actor=getuser(),
        note="Blue suitcase",
    )
    for claim in list_claims(connection, status="open", tier="gold"):
        print(claim["id"], claim["status"], claim["deadline"])
```

In a new database the example prints `1 open 2026-11-02T18:00:00+00:00`. Filing records `NULL → open` history with the supplied actor and timestamp. Gold receives 4 hours, silver 24 hours, and standard 72 hours. Offset-free datetime input means UTC; offset-bearing input is converted to UTC. Listing combines filters with AND, orders by ID, and returns each matching claim once.

The status APIs are `assign_claim(connection, claim_id, *, agent, now, actor)`, `resolve_claim(connection, claim_id, *, now, actor)`, and `close_claim(connection, claim_id, *, now, actor)`. Assign open/escalated claims to a nonblank agent, resolve assigned/escalated claims, and close resolved claims. Closed claims are terminal. Resolution and closure preserve ownership and unrelated fields. `get_history(connection, claim_id)` returns complete history mappings in entry-ID order. Missing IDs and forbidden changes raise clear `ValueError`s without writes.

Standalone filing and status operations commit the claim and its history together. To group operations into one batch, explicitly start an outer transaction before the first call:

```python
with connection:
    connection.execute("BEGIN")
    # Call file_claim(connection, ...) for each validated row here.
    # An exception escaping this block rolls back the entire batch.
```

Connection contexts manage transactions; `closing(...)` closes the database connection. Filing and status operations use savepoints and never commit an existing caller transaction. This supports the later all-or-nothing CSV importer without weakening individual claim/history atomicity. Every rule receives time and actor from its caller; only the future CLI will read the clock and choose the manual actor.

## Testing

The reviewed filing/schema suite is in [tests/test_claims.py](tests/test_claims.py). Assignment/status/history tests are in [tests/test_status.py](tests/test_status.py). With the project virtual environment active:

```text
python -m pytest
python -m pytest tests/test_claims.py
python -m pytest tests/test_status.py
python -m ruff check .
```

Current branch result: **115 cases pass; Ruff passes**. The status tests cover allowed paths, forbidden changes, validation, complete ordered history, UTC times, and transaction rollback/commit. Commit `1501cb4` preserves the 46 failing status cases before implementation commit `4f727b8`; neither test file changed during implementation, and no additional cases were added. Run the documented commands from the repository root. See [the implementation log](docs/PROMPT_LOG.md#17--complete-the-assignment-and-status-branch-workflow) for actual checks and review evidence.

The test-first history is preserved: [initial 31-case red run](docs/ORB-56-pytest-red.txt), [reviewed 69-case red run](docs/ORB-56-pytest-red-69.txt), then tests-only commit `ef67f61` before any application implementation. See the [test review and implementation log](docs/PROMPT_LOG.md#13--complete-orb-52-against-the-reviewed-tests).

The [rollback mutation check](docs/ORB-52-rollback-mutation.txt) removed filing's transaction context in a temporary copy. The unchanged rollback test failed against that deliberate defect; the normal implementation passes it. Temporary copies do not alter or weaken the committed tests.

For status operations, removing only their transaction context in a temporary copy caused all three forced-history-failure cases to fail. The real implementation passes these unchanged tests. The actual Stop hook ran the completed branch's 115 cases successfully and returned `{}` with exit 0.

A fresh local checkout of implementation commit `ef80b49`, with a newly created virtual environment and dependencies installed from `requirements-dev.txt`, passed all 69 cases and Ruff without optional pytest configuration. The actual Stop hook also returned successful JSON `{}` with all 69 cases passing, so it required no continuation.

## Linear Issues

Project: [Orbit Air Baggage Desk](https://linear.app/orbit-air-baggage-desk/project/orbit-air-baggage-desk-8930c0fcca68).

| Issue | Required branch | Minimum new tests | Depends on |
|---|---|---|---|
| [ORB-52 — Persist and file baggage claims](https://linear.app/orbit-air-baggage-desk/issue/ORB-52/featureschema-and-filing-persist-and-file-baggage-claims) | `feature/schema-and-filing` | 5 | None |
| [ORB-53 — Enforce claim transitions and history](https://linear.app/orbit-air-baggage-desk/issue/ORB-53/featureassign-and-status-enforce-claim-transitions-and-history) | `feature/assign-and-status` | 6 | ORB-52 |
| [ORB-54 — Escalate overdue claims atomically](https://linear.app/orbit-air-baggage-desk/issue/ORB-54/featuredeadlines-and-escalation-escalate-overdue-claims-atomically) | `feature/deadlines-and-escalation` | 6 | ORB-53 |
| [ORB-55 — Expose claim commands and CSV seeding](https://linear.app/orbit-air-baggage-desk/issue/ORB-55/featurecli-expose-claim-commands-and-csv-seeding) | `feature/cli` | 3 | ORB-54 |

All four issues were created in Backlog and include Problem, Actual behavior, Expected behavior, Done when, and Constraint sections. Follow the exact branch names above rather than Linear's generated suggestions. ORB-52 is Done after [PR #2](https://github.com/AbdulMB-Online/Orbit-Air-Baggage-Desk/pull/2) merged. ORB-53 is implemented and verified on `feature/assign-and-status`; its parent remains open for PR review and merge.

### Scoped sub-issues

Each parent has four linked sub-issues. Open the parent in Linear to view its children. They share the parent's exact branch and single PR; the parent's test minimum applies across its children.

| Parent | Tests first | Implementation step 1 | Implementation step 2 | Final step |
|---|---|---|---|---|
| ORB-52 | [ORB-56 — Filing/schema tests](https://linear.app/orbit-air-baggage-desk/issue/ORB-56) | [ORB-57 — SQLite schema](https://linear.app/orbit-air-baggage-desk/issue/ORB-57) | [ORB-58 — Filing/history](https://linear.app/orbit-air-baggage-desk/issue/ORB-58) | [ORB-59 — Listing and verification](https://linear.app/orbit-air-baggage-desk/issue/ORB-59) |
| ORB-53 | [ORB-60 — Transition/history tests](https://linear.app/orbit-air-baggage-desk/issue/ORB-60) | [ORB-61 — Assignment/guards](https://linear.app/orbit-air-baggage-desk/issue/ORB-61) | [ORB-62 — Resolution/closure](https://linear.app/orbit-air-baggage-desk/issue/ORB-62) | [ORB-63 — History and verification](https://linear.app/orbit-air-baggage-desk/issue/ORB-63) |
| ORB-54 | [ORB-64 — Overdue/escalation tests](https://linear.app/orbit-air-baggage-desk/issue/ORB-64) | [ORB-65 — Overdue eligibility](https://linear.app/orbit-air-baggage-desk/issue/ORB-65) | [ORB-66 — Batch escalation](https://linear.app/orbit-air-baggage-desk/issue/ORB-66) | [ORB-67 — Rollback and review](https://linear.app/orbit-air-baggage-desk/issue/ORB-67) |
| ORB-55 | [ORB-68 — CLI/seed tests](https://linear.app/orbit-air-baggage-desk/issue/ORB-68) | [ORB-69 — Commands/clock](https://linear.app/orbit-air-baggage-desk/issue/ORB-69) | [ORB-70 — Atomic CSV seeding](https://linear.app/orbit-air-baggage-desk/issue/ORB-70) | [ORB-71 — Walkthrough/final review](https://linear.app/orbit-air-baggage-desk/issue/ORB-71) |

All sub-issues were created in Backlog. Each step depends on the preceding sibling; the first child of ORB-53, ORB-54, and ORB-55 also waits for its parent's prerequisite issue. Keep each parent open until its children, acceptance checks, and required PR merge are complete. ORB-56 through ORB-62 are Done; ORB-63 is In Progress for the PR handoff, review, and merge workflow.

## Setup Check

Codex was asked to use the filesystem deny profile and trusted pytest Stop hook in `.codex/config.toml`. On 2026-11-05, checks against temporary empty root and nested `.env` probes were repeated in the actual Codex sandbox after an initial nonexistent-file probe proved inconclusive. Both opens were denied with errno 1, while `PLAN.md` remained openable. No `.env` contents were read or printed, and the probes were removed. Details and the observed corrections are in [log entry 05](docs/PROMPT_LOG.md#05--configure-and-verify-security-controls).

The local Codex 0.163.0 hook UI showed the hook as **Trusted**, with one installed and one active Stop hook. Hook trust is local to each installation and must be reviewed normally in another clone or after changes requiring review.

During the intentionally red tests-only phase, the original hook repeatedly restarted the turn. The user separately approved a loop guard: pytest still runs, an initial failure exits 2, and a repeated failure ends the turn with an explicit unsuccessful-validation warning. This does not report failing tests as passing. The guard was checked with passing/failing/no-tests/missing-environment fixtures and the actual 69-case red suite. The implemented first feature now passes normally; see [log entry 12](docs/PROMPT_LOG.md#12--fix-the-stop-hook-loop-with-explicit-approval).

## Agent Log

Codex assists with development. The [detailed prompt log](docs/PROMPT_LOG.md) records substantive prompts, decisions, corrections, and observed review outcomes. The user merged the first feature in PR #2; the second feature is implemented and verified, awaiting its dedicated PR review and merge.

| Entry | Prompt summary | Work and review outcome |
|---|---|---|
| [01 — Lab context](docs/PROMPT_LOG.md#01--understand-the-lab) | Read the lab and gain detailed context. | Inspected requirements and repository state; identified exact names, test-first history, and evidence requirements. |
| [02 — Project plan](docs/PROMPT_LOG.md#02--create-and-review-the-plan) | Create `PLAN.md` with rules, schema, branches, tests, risks, and PR strategy. | Created the reviewed plan. User selected UTC normalization, OS usernames for manual history, and atomic CSV imports. |
| [03 — Codex adaptation](docs/PROMPT_LOG.md#03--adapt-tooling-to-codex) | Replace agent-specific tooling references with Codex counterparts. | Updated the plan for Codex instructions, configuration, permissions, hooks, and review; flagged unverified grader acceptance. |
| [04 — Project instructions](docs/PROMPT_LOG.md#04--write-project-instructions) | Add architecture boundaries, pytest/Ruff commands, test-first rules, security, and approval before editing existing tests. | Wrote and checked a 29-line `AGENTS.md`; no application code or tests were created. |
| [05 — Security controls](docs/PROMPT_LOG.md#05--configure-and-verify-security-controls) | Use the planned filesystem deny policy and trusted pytest Stop hook. | Verified root/nested `.env` denial without reading contents and hook behavior in temporary fixtures; reviewed and trusted the hook. Corrected unsupported CLI validation and inconclusive probes. |
| [06 — Prompt logging](docs/PROMPT_LOG.md#06--establish-prompt-logging) | Maintain a detailed prompt log and relevant README summaries. | Added linked documentation and a durable logging instruction; preserved the existing README headings. |
| [07 — Next feature planning](docs/PROMPT_LOG.md#07--fetch-updates-and-plan-the-first-feature) | Fetch pushed updates and plan the next build. | Confirmed setup PR #1 is merged; proposed `feature/schema-and-filing` next. Identified the untracked prompt log, joined ignore entry, missing project environment, and empty Linear project as preparation work. |
| [08 — Linear issues](docs/PROMPT_LOG.md#08--create-the-four-required-linear-issues) | Create the required Linear issues and explain the workflow. | Created ORB-52 through ORB-55 with exact branch prefixes, all five required sections, test-first criteria, and sequential dependencies; verified the saved content and added links above. |
| [09 — Scoped sub-issues](docs/PROMPT_LOG.md#09--scope-each-parent-into-four-sub-issues) | Add 2–4 sub-issues per parent for scoped, trackable development. | Created 16 real children, ORB-56 through ORB-71, verified parent links and dependencies, and added a sub-issue index to each parent and this README. |
| [10 — First failing tests](docs/PROMPT_LOG.md#10--write-and-run-orb-56-tests-without-implementation) | Read ORB-52 and its children, write at least five tests, and report expected failures; implementation and commits prohibited. | Added 14 test functions yielding 31 collected cases. All 31 failed because `db.py` is absent; no collection errors, skips, or xfails. Ruff passed; captured the real output. |
| [11 — Test audit and strengthening](docs/PROMPT_LOG.md#11--audit-and-strengthen-the-reviewed-tests) | Audit tests read-only, then fix six findings using test-file changes only. | Strengthened filters, history preservation, schema constraints, rejection snapshots, duplicate detection, and observer cleanup. Added caller-transaction checks; 69 expected red cases and clean Ruff. User reviewed the result and said “looks good.” |
| [12 — Hook loop correction](docs/PROMPT_LOG.md#12--fix-the-stop-hook-loop-with-explicit-approval) | Explain the repeated Stop hook and fix only its loop after explicit approval. | Added a continuation-state guard without editing tests or treating failures as passes. Verified initial and repeated failure behavior against the actual suite. |
| [13 — `feature/schema-and-filing`](docs/PROMPT_LOG.md#13--complete-orb-52-against-the-reviewed-tests) | Complete the current issue and prepare the PR handoff; user will create, review, and merge it. | Committed reviewed tests first (`ef67f61`), then implemented SQLite schema, validated filing, atomic initial history, UTC deadlines, and filtered listing. All 69 tests and Ruff pass. Removing transaction protection in a temporary copy caused the rollback test to fail as intended. |
| [14 — First feature merged](docs/PROMPT_LOG.md#14--verify-the-first-feature-merge) | User reported the PR merged. | Verified PR #2 merge `f753d57`, synchronized local main, re-ran all 69 cases and Ruff successfully, and marked ORB-52/ORB-59 Done. No new feature branch or implementation was started. |
| [15 — Assignment/status tests first](docs/PROMPT_LOG.md#15--write-assignment-status-and-history-tests-first) | Write at least six tests for assignment, resolution, closure, allowed changes, and history. | Added 13 functions covering 46 cases, including rejection without writes and forced history failure. Full pytest: 69 existing pass, 46 expected failures at missing APIs. Ruff passes. Existing tests and application code unchanged; API choices documented for review; no branches or commits. |
| [16 — Assignment scope](docs/PROMPT_LOG.md#16--limit-future-work-to-assignment-requirements) | Explain the 100+ cases and limit future work to assignment requirements. | Acknowledged excessive coverage and updated project instructions to use focused tests for required rules and branch minimums. Existing tests remain unchanged; no implementation or commits. |
| [17 — `feature/assign-and-status`](docs/PROMPT_LOG.md#17--complete-the-assignment-and-status-branch-workflow) | Proceed with the required branch workflow. | Created the exact branch from current main; committed failing tests first (`1501cb4`), then implemented atomic assignment, resolution, closure, and ordered history (`4f727b8`). All 115 cases and Ruff pass; all three rollback cases detect removal of transaction protection in a temporary copy. No tests or unrelated features were added during implementation. PR creation/review/merge remains with the user. |

ORB-56 created the ignored project virtual environment with pytest and Ruff. Both feature suites have separate tests-first commits and are green. Their frozen file hashes are recorded in the prompt log. Temporary hook and mutation fixtures do not count toward application tests.

### Feature branch evidence pending

| Required branch | Minimum tests | Status |
|---|---|---|
| `feature/schema-and-filing` | 5 | PR #2 merged as `f753d57`; 69 passing cases; separate test-first history preserved |
| `feature/assign-and-status` | 6 | Separate tests-first and implementation commits; all 115 cases and Ruff pass; dedicated PR review/merge pending |
| `feature/deadlines-and-escalation` | 6 | Implementation, test-first results, and PR review pending |
| `feature/cli` | 3 | Implementation, test-first results, and PR review pending |

Add actual branch prompts, Codex changes, learner checks/corrections, and review outcomes as work happens. Acceptance of the user-requested Codex tooling substitutions by the original assignment grader is unverified.

## Hidden Instruction Check

The required seed-file summary exercise is pending `feature/cli`; it has not been claimed as complete. The current filing test verifies that quoted, SQL-like note text is stored literally. Notes must remain data, and `.env` must never be disclosed.

## Overdue Demonstration

Pending `feature/deadlines-and-escalation` and `feature/cli`. This first feature calculates deadlines but does not yet provide the escalation command or a `--now` CLI demonstration.

## Code Review

At the user's request, Codex audited the first test draft and corrected six findings. The user approved the strengthened result with “looks good” before implementation. Codex self-reviewed the implementation against those frozen tests and checked rollback sensitivity. Ruff flagged two Python argument-type guards; these were corrected to use `TypeError` for invalid `now`/`note` argument types while preserving `ValueError` for invalid claim values.

For `feature/assign-and-status`, Codex self-reviewed the diff against the transition map, atomic-history rule, field preservation, and injected time/actor policy. All frozen tests and Ruff passed without test changes; the rollback sensitivity check caught removal of transaction protection. Learner review of this implementation is pending.

The user reported PR #2 merged, and the merge was verified in Git. No detailed review findings were supplied, and an independent PR review has not been claimed. The final `codex review --base main` evidence belongs to the later CLI PR, as planned.
