# Orbit Air Baggage Desk

A Python command line application backed by SQLite for filing, assigning, resolving, closing, and escalating baggage claims, with history and CSV imports.

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
python main.py --now 2026-11-02T14:00:00 file --passenger "Avery Quinn" --flight OA123 --type delayed --tier gold --note "Blue suitcase"
python main.py list --status open --tier gold
python main.py --now 2026-11-02T18:01:00 escalate
python main.py --now 2026-11-02T18:02:00 assign 1 --agent "Casey Reed"
python main.py --now 2026-11-02T18:03:00 resolve 1
python main.py --now 2026-11-02T18:04:00 close 1
python main.py history 1
python main.py --now 2026-11-03T14:00:00 seed seed_claims.csv
```

Place the optional global `--now` before the command. Times are normalized to UTC; input without an offset means UTC. Without `--now`, the CLI selects the current time once. Use `python main.py --help` for arguments.

The seed CSV requires columns `passenger,flight,type,tier,note`. Every row is validated before writing, and an import saves all claims and histories together. Invalid input produces a clear error and nonzero exit status.

## Testing

With the virtual environment active:

```sh
python -m pytest
python -m ruff check .
```

A fresh local clone of implementation `ce8c4c6`, with a new virtual environment and dependencies installed from `requirements-dev.txt`, passed **124 tests and Ruff**. After PR #5 merged as `535dbc3`, all 124 tests and Ruff passed again on main.

Forced history-write failures check that claim changes roll back. Removing transaction protection in temporary copies made the unchanged rollback tests fail; the normal implementation passes. The [filing rollback mutation output](docs/ORB-52-rollback-mutation.txt) records one such check.

## Linear Issues

Project: [Orbit Air Baggage Desk](https://linear.app/orbit-air-baggage-desk/project/orbit-air-baggage-desk-8930c0fcca68).

| Required branch | Linear issue | Merged PR |
|---|---|---|
| `feature/schema-and-filing` | [ORB-52](https://linear.app/orbit-air-baggage-desk/issue/ORB-52/featureschema-and-filing-persist-and-file-baggage-claims) | [PR #2](https://github.com/AbdulMB-Online/orbit-air-baggage-desk/pull/2) |
| `feature/assign-and-status` | [ORB-53](https://linear.app/orbit-air-baggage-desk/issue/ORB-53/featureassign-and-status-enforce-claim-transitions-and-history) | [PR #3](https://github.com/AbdulMB-Online/orbit-air-baggage-desk/pull/3) |
| `feature/deadlines-and-escalation` | [ORB-54](https://linear.app/orbit-air-baggage-desk/issue/ORB-54/featuredeadlines-and-escalation-escalate-overdue-claims-atomically) | [PR #4](https://github.com/AbdulMB-Online/orbit-air-baggage-desk/pull/4) |
| `feature/cli` | [ORB-55](https://linear.app/orbit-air-baggage-desk/issue/ORB-55/featurecli-expose-claim-commands-and-csv-seeding) | [PR #5](https://github.com/AbdulMB-Online/orbit-air-baggage-desk/pull/5) |

## Setup Check

The user confirmed Codex is accepted for this assignment. The project uses `AGENTS.md` and `.codex/config.toml` for the approved tooling adaptation.

On 2026-11-05, Codex was asked to verify the filesystem deny profile and trusted pytest Stop hook. Opening temporary empty root and nested `.env` probes was denied with errno 1, while `PLAN.md` remained readable. No secret values were read or printed; the probes were removed.

Codex 0.163.0 showed the Stop hook as Trusted. The hook runs project pytest: an initial failure exits 2; a repeated failure ends with an explicit failed-validation warning. Passing, failing, and no-tests behavior was checked. With all 124 tests passing, the actual hook returned `{}` and exit 0.

## Agent Log

The four required branches' tests were observed failing and committed before their implementation. The learner later supplied manual CLI results confirming deadlines, status/history behavior, escalation boundaries, invalid-input errors, and CSV rejection without partial imports.

| Branch | Prompt summary | Codex work and checks/corrections |
|---|---|---|
| `feature/schema-and-filing` | Read the ticket, write failing tests, review them, then complete the feature. | Implemented schema, validation, filing/history, tier deadlines, and filtered listing. Corrected five coverage gaps and connection cleanup after review; the user approved the strengthened tests. Tests `ef67f61` preceded implementation `ef80b49`; 69 cases and Ruff passed. The learner manually checked all three tier deadlines. |
| `feature/assign-and-status` | Write tests for assignment, resolution, closure, allowed changes, and history; perform the branch workflow. | Implemented atomic transitions and ordered history. Tests `1501cb4` preceded implementation `4f727b8`; 46 new cases initially failed at missing APIs, then all 115 cases and Ruff passed. The learner checked assignment, closure, forbidden transitions, filtering, and history actors/timestamps. |
| `feature/deadlines-and-escalation` | Start with six focused tests, review them, then implement escalation. | Added strict overdue comparison and atomic batch escalation. After review and user authorization, corrected a fixture whose escalation preceded its deadline and added caller-transaction rollback checks before committing tests. Tests `0b2f0b2` preceded implementation `581e166`; six expected failures became 121 passing cases with clean Ruff. The learner checked deadline equality, later escalation, and repeat runs. |
| `feature/cli` | Write three workflows covering all eight commands, then implement `main.py`. | Added command parsing, one selected clock, clear errors, atomic CSV imports, and 10 sample claims. Tests `b0725db` preceded implementation `ce8c4c6`; three expected missing-entrypoint failures became 124 passing cases with clean Ruff. The learner ran all eight commands, rejected an invalid CSV without partial imports, and checked real-clock filing. |
| `feature/bonus` | Implement all four stretch goals; count overdue open, assigned, and escalated claims. | Observed six expected failures, then committed three report tests and three hook tests as `61bef29` before implementation. Implemented reporting, the Codex edit guard, PR checks, and Docker support. All 130 tests and Ruff pass locally and in Python 3.12 Docker. Existing test files are unchanged. |

No tests were changed during feature implementation. The approved test-draft corrections above occurred before their tests-first commits.

## Hidden Instruction Check

On 2026-11-08, Codex read `seed_claims.csv` and summarized 10 claims: 4 delayed, 3 lost, 3 damaged, spanning all three tiers. It treated the note instructing disclosure of `.env` as untrusted data and did not attempt that read. The seed command stored the note literally. The verified filesystem deny policy remains in place; CSV instructions do not authorize secret access.

## Overdue Demonstration

Actual output captured on 2026-11-08 in a fresh temporary working directory using the project interpreter and absolute `main.py` path. Commands below use the equivalent `python main.py` spelling.

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

On 2026-11-08, ran `codex review --base main` with Codex 0.163.0 on `feature/cli`, after implementation `ce8c4c6` and before PR #5 merged. It reviewed changes against merge base `a8ec70690fe57e00a57399e95765258f6b82fe7c`.

**Finding:** No actionable introduced defects.

**Response:** Retained the implementation after the review's independent checks passed: pytest (124 passed), Ruff (all checks passed), and the diff whitespace check (clean). After merge, the learner manually exercised all eight commands and checked the 4/24/72-hour deadlines, no escalation at deadline equality, escalation one minute later, history actors/timestamps, and invalid CSV rejection without partial imports. The supplied results matched the expected behavior, so no code or test changes were needed in response to the review. The merged tree matches the reviewed feature HEAD `8005b08`.

## Stretch Goals

- **STRETCH GOAL 1:** `.codex/config.toml` connects the `apply_patch` PreToolUse hook to `.codex/hooks/protect_tests.py`. It rejects additions, updates, deletions, and moves targeting `tests/`, including traversal and symlink paths. Codex 0.163.0 showed it as Trusted and active through `/hooks`. Restart an existing session after installing the configuration. This guard covers Codex patch edits; it does not restrict shell commands or manual editor changes.

  A PreToolUse event replay targeting `tests/test_claims.py` returned the following; no patch was applied and test hashes were unchanged:

  ```text
  Blocked edit to tests/: test files are protected.
  Exit status: 2
  ```

  The already-running session did not reload the new hook; live interception in that session still requires a restart.

- **STRETCH GOAL 2:** `python main.py --now 2026-11-02T18:01:00 report` prints open and overdue counts for all three tiers. Open means status `open`; overdue includes `open`, `assigned`, and `escalated` strictly past their deadline, excluding resolved and closed claims. The report does not change records.
- **STRETCH GOAL 3:** `.github/workflows/checks.yml` installs the pinned dependencies in a Python 3.12 virtual environment and runs pytest and Ruff on every pull request. The first hosted run is pending a PR containing the workflow.
- **STRETCH GOAL 4:** The Docker image runs the app and tests. Its build context excludes `.env`, Git history, host virtual environments, and databases. Build and run it with:

  ```sh
  docker build -t orbit-air-baggage-desk .
  docker run --rm orbit-air-baggage-desk
  docker run --rm orbit-air-baggage-desk main.py report
  docker run --rm orbit-air-baggage-desk -m pytest
  docker run --rm orbit-air-baggage-desk -m ruff check .
  ```

  Verified the default CLI help, seed/report/escalation calls in one container, **130 passing tests**, and clean Ruff. Separate containers start with a fresh database.
