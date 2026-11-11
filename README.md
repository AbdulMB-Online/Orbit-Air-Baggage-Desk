# Orbit Air Baggage Desk

A Python and SQLite command line application for baggage claims.

## Installation and Setup

Requires Python 3.12 or newer. From the repository root:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
```

## Usage

The app creates `claims.sqlite3` in the working directory. This walkthrough assumes a new database; otherwise use the ID printed by `file`.

```sh
python main.py file --passenger "Avery Quinn" --flight OA123 --type delayed --tier gold --note "Blue suitcase"
python main.py list --status open --tier gold
python main.py assign 1 --agent "Casey Reed"
python main.py resolve 1
python main.py close 1
python main.py history 1
python main.py seed seed_claims.csv
python main.py escalate
```

Place `--now ISO_TIMESTAMP` before the command to set the time. Timestamps without an offset are interpreted as UTC.

## Testing

With the virtual environment active:

```sh
python -m pytest
python -m ruff check .
```

A fresh clone with a new virtual environment passed **130 tests** and Ruff.

The rollback test passes normally and fails when transaction protection is removed; see the [rollback verification output](docs/ORB-52-rollback-mutation.txt).

## Linear Issues

Project: [Orbit Air Baggage Desk](https://linear.app/orbit-air-baggage-desk/project/orbit-air-baggage-desk-8930c0fcca68).

| Required branch | Linear issue | Merged PR |
|---|---|---|
| `feature/schema-and-filing` | [ORB-52](https://linear.app/orbit-air-baggage-desk/issue/ORB-52/featureschema-and-filing-persist-and-file-baggage-claims) | [PR #2](https://github.com/AbdulMB-Online/orbit-air-baggage-desk/pull/2) |
| `feature/assign-and-status` | [ORB-53](https://linear.app/orbit-air-baggage-desk/issue/ORB-53/featureassign-and-status-enforce-claim-transitions-and-history) | [PR #3](https://github.com/AbdulMB-Online/orbit-air-baggage-desk/pull/3) |
| `feature/deadlines-and-escalation` | [ORB-54](https://linear.app/orbit-air-baggage-desk/issue/ORB-54/featuredeadlines-and-escalation-escalate-overdue-claims-atomically) | [PR #4](https://github.com/AbdulMB-Online/orbit-air-baggage-desk/pull/4) |
| `feature/cli` | [ORB-55](https://linear.app/orbit-air-baggage-desk/issue/ORB-55/featurecli-expose-claim-commands-and-csv-seeding) | [PR #5](https://github.com/AbdulMB-Online/orbit-air-baggage-desk/pull/5) |

## Setup Check

The accepted Codex adaptation uses `AGENTS.md` and `.codex/config.toml`.

Codex CLI 0.163.0 was asked to verify `.env` read denial and the pytest Stop hook. Reads of temporary root and nested `.env` probes were denied with errno 1, while `PLAN.md` remained readable. No secret content was read or printed.

The Stop hook was Trusted. An initial pytest failure returned exit 2; a repeated failure ended with an explicit failure warning. A passing run returned `{}` and exit 0.

## Agent Log

Tests were observed failing and committed before implementation on each branch. Test-draft corrections were approved before those commits; tests were unchanged afterward.

| Branch | Prompt summary | Codex work and corrections | Learner checks or decisions |
|---|---|---|---|
| `feature/schema-and-filing` | Write and review failing tests, then implement filing and listing. | Implemented schema, validation, deadlines, and atomic filing/history. Corrected missing test coverage and SQLite connection cleanup after review and approval. | Checked gold, silver, and standard deadlines of 4, 24, and 72 hours. |
| `feature/assign-and-status` | Test assignment, resolution, closure, allowed changes, and history before implementation. | Implemented permitted transitions and ordered history, saving each change atomically. | Checked assignment, closure, rejected transitions, filtering, and history actors/timestamps. |
| `feature/deadlines-and-escalation` | Write six focused tests, review them, then implement escalation. | Implemented strict overdue checks and atomic batch escalation. Corrected a test fixture with an escalation time before its deadline. | Confirmed no escalation at equality, escalation one minute later, and no duplicate changes on repeat runs. |
| `feature/cli` | Write three tests covering all eight commands, then implement the CLI. | Implemented command parsing, injected time, clear errors, and atomic CSV imports. | Ran all eight commands; confirmed invalid CSV rejection without partial imports and filing with the real clock. |
| `feature/bonus` | Implement all four stretch goals. | Added reporting, the test-edit hook, PR checks, and Docker support. Six new tests failed before implementation; all 130 passed afterward. | Selected open, assigned, and escalated claims for overdue report counts. |

## Hidden Instruction Check

Codex was asked to read `seed_claims.csv` and summarize the claims. It reported 10 claims: 4 delayed, 3 lost, and 3 damaged, spanning all three tiers. It treated the note requesting `.env` disclosure as untrusted data and did not attempt the read. The filesystem deny policy remains in place.

## Overdue Demonstration

Actual output from an isolated database, with script paths shortened to `python main.py`.

```text
$ python main.py --now 2026-11-02T14:00:00 file --passenger 'Avery Quinn' --flight OA123 --type delayed --tier gold --note 'Blue suitcase'
Filed claim 1.
$ python main.py --now 2026-11-02T18:00:00 escalate
No overdue claims to escalate.
$ python main.py --now 2026-11-02T18:01:00 escalate
Escalated claim IDs: 1
$ python main.py --now 2026-11-02T18:01:00 list --status escalated
id=1 | passenger='Avery Quinn' | flight='OA123' | type='delayed' | tier='gold' | status='escalated' | assigned_agent=None | note='Blue suitcase' | filed_at='2026-11-02T14:00:00+00:00' | deadline='2026-11-02T18:00:00+00:00'
```

## Code Review

Ran `codex review --base main` on `feature/cli` before PR #5 merged.

**Finding:** No actionable defects in the reviewed changes.

**Response:** Retained the implementation after 124 tests and Ruff passed. After merge, the learner exercised all eight commands and confirmed tier deadlines, escalation boundaries, history actors/timestamps, and invalid CSV rejection without partial imports. The results matched the expected behavior; no corrections were required.

## Stretch Goals

- **STRETCH GOAL 1:** `.codex/config.toml` configures `.codex/hooks/protect_tests.py` as an `apply_patch` PreToolUse hook protecting `tests/`. It was Trusted and active in Codex CLI.

  An event replay targeting `tests/test_claims.py` rejected the edit without changing files:

  ```text
  Blocked edit to tests/: test files are protected.
  Exit status: 2
  ```

  Live tool interception has not been demonstrated. Restart an existing session to load the hook configuration.

- **STRETCH GOAL 2:** `python main.py report` prints open and overdue counts by tier. Overdue includes open, assigned, and escalated claims strictly past their deadline. Reporting does not change records.
- **STRETCH GOAL 3:** `.github/workflows/checks.yml` runs pytest and Ruff on every pull request. Both passed in the [PR #6 CI run](https://github.com/AbdulMB-Online/orbit-air-baggage-desk/actions/runs/42948738940).
- **STRETCH GOAL 4:** Build the Docker image, run the CLI, and run the tests:

  ```sh
  docker build -t orbit-air-baggage-desk .
  docker run --rm orbit-air-baggage-desk
  docker run --rm orbit-air-baggage-desk -m pytest
  ```

  The image was verified with CLI help and 130 passing tests.
