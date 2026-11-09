# Orbit Air Baggage Desk

## Overview

Orbit Air Baggage Desk manages baggage claims in SQLite. The CLI and Python API support filing, deadlines, filtered listing, assignment, resolution, closure, audit history, automatic overdue escalation, and atomic CSV imports.

## Installation and Setup

Requires Python 3.12 or newer. From the repository root:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
```

The application uses the Python standard library; `requirements-dev.txt` supplies pinned pytest and Ruff versions. Keep local SQLite databases, their journal/WAL files, virtual environments, and `.env` out of Git.

## Usage

Run from the repository root with the virtual environment active. The app creates `claims.sqlite3` in the working directory. These examples assume a new database; use the IDs printed by `file` when working with existing data.

```sh
python main.py --now 2026-11-02T14:00:00 file --passenger "Avery Quinn" --flight OA123 --type delayed --tier gold --note "Blue suitcase"
python main.py --now 2026-11-02T14:00:00 list --status open --tier gold
python main.py --now 2026-11-02T18:01:00 escalate
python main.py --now 2026-11-02T18:02:00 assign 1 --agent "Casey Reed"
python main.py --now 2026-11-02T18:03:00 resolve 1
python main.py --now 2026-11-02T18:04:00 close 1
python main.py history 1
python main.py --now 2026-11-03T14:00:00 seed seed_claims.csv
```

All eight commands support the global `--now` option before the command. Without it, the CLI selects the current UTC time once per invocation. Offset-free input means UTC; offset-bearing input is converted to UTC. Manual history uses the local OS username; automatic escalation uses `system`.

Gold receives 4 hours, silver 24, and standard 72. A claim is overdue only after its deadline. Assignment accepts open/escalated claims; resolution accepts assigned/escalated claims; closure accepts resolved claims. Closed claims are terminal. List filters combine with AND; history is scoped to one claim and ordered by entry ID.

CSV columns must be exactly `passenger,flight,type,tier,note`. The sample has 10 claims spanning all types and tiers. All rows are validated before writing; each import and its initial histories commit together. Bad input gives a clear stderr error and nonzero exit status without partial claim writes. Notes remain literal data, including quoted commas and newlines.

Business APIs remain in `claims.py`; their savepoints preserve an existing caller transaction. The CLI closes its database connection after every command. Use `python main.py --help` or a command's `--help` for arguments.

## Testing

The reviewed business suites are in [tests/test_claims.py](tests/test_claims.py), [tests/test_status.py](tests/test_status.py), and [tests/test_escalation.py](tests/test_escalation.py). The three CLI workflows are in [tests/test_cli.py](tests/test_cli.py). With the project virtual environment active:

```text
python -m pytest
python -m pytest tests/test_claims.py
python -m pytest tests/test_status.py
python -m pytest tests/test_escalation.py
python -m pytest tests/test_cli.py
python -m ruff check .
```

Current result: **124 cases pass; Ruff passes**. The three CLI workflows execute all eight required commands, injected/real time behavior, CSV quoting and sample data, clear errors, and atomic imports. Tests-first commit `b0725db` precedes implementation `ce8c4c6`; all tests remain unchanged.

On 2026-11-08, a fresh local clone of `feature/cli` at `ce8c4c6`, with a newly created virtual environment and dependencies installed from `requirements-dev.txt`, passed **124 tests in 1.10s** and Ruff. This used Python 3.15.0, pytest 9.2.0, and Ruff 0.17.3, with no optional pytest configuration or shared environment packages.

The completed escalation branch adds exactly six focused cases covering boundaries/UTC, eligibility/IDs, history within a caller-owned transaction, empty batches, repeat execution, and whole-batch rollback. Tests-first commit `0b2f0b2` precedes implementation `581e166`; the three committed business test files remain unchanged. The two draft corrections were made before committing escalation tests; see [the review log](#agent-log) and [implementation evidence](#agent-log).

The completed status tests cover allowed paths, forbidden changes, validation, complete ordered history, UTC times, and transaction rollback/commit. Commit `1501cb4` preserves their failing cases before implementation commit `4f727b8`; both existing test files remain unchanged. See [the implementation log](#agent-log) for those checks.

The test-first history is preserved: [initial 31-case red run](docs/ORB-56-pytest-red.txt), [reviewed 69-case red run](docs/ORB-56-pytest-red-69.txt), then tests-only commit `ef67f61` before any application implementation. See the [test review and implementation log](#agent-log).

The [rollback mutation check](docs/ORB-52-rollback-mutation.txt) removed filing's transaction context in a temporary copy. The unchanged rollback test failed against that deliberate defect; the normal implementation passes it. Temporary copies do not alter or weaken the committed tests.

For status operations, removing only their transaction context in a temporary copy caused all three forced-history-failure cases to fail. The real implementation passes these unchanged tests. The actual Stop hook ran the completed branch's 115 cases successfully and returned `{}` with exit 0.

For escalation, removing only the outer batch savepoint in a temporary copy left per-claim protection intact but caused the unchanged batch rollback test to fail on partial claim/history writes. The real implementation passes it and the caller-owned transaction checks. The actual Stop hook passed all 121 cases and returned `{}` with exit 0.

A fresh local checkout of implementation commit `ef80b49`, with a newly created virtual environment and dependencies installed from `requirements-dev.txt`, passed all 69 cases and Ruff without optional pytest configuration. The actual Stop hook also returned successful JSON `{}` with all 69 cases passing, so it required no continuation.

## Linear Issues

Project: [Orbit Air Baggage Desk](https://linear.app/orbit-air-baggage-desk/project/orbit-air-baggage-desk-8930c0fcca68).

| Issue | Required branch | Minimum new tests | Depends on |
|---|---|---|---|
| [ORB-52 — Persist and file baggage claims](https://linear.app/orbit-air-baggage-desk/issue/ORB-52/featureschema-and-filing-persist-and-file-baggage-claims) | `feature/schema-and-filing` | 5 | None |
| [ORB-53 — Enforce claim transitions and history](https://linear.app/orbit-air-baggage-desk/issue/ORB-53/featureassign-and-status-enforce-claim-transitions-and-history) | `feature/assign-and-status` | 6 | ORB-52 |
| [ORB-54 — Escalate overdue claims atomically](https://linear.app/orbit-air-baggage-desk/issue/ORB-54/featuredeadlines-and-escalation-escalate-overdue-claims-atomically) | `feature/deadlines-and-escalation` | 6 | ORB-53 |
| [ORB-55 — Expose claim commands and CSV seeding](https://linear.app/orbit-air-baggage-desk/issue/ORB-55/featurecli-expose-claim-commands-and-csv-seeding) | `feature/cli` | 3 | ORB-54 |

All four issues were created in Backlog and include Problem, Actual behavior, Expected behavior, Done when, and Constraint sections. Follow the exact branch names above rather than Linear's generated suggestions. ORB-52, ORB-53, and ORB-54 are Done after [PR #2](https://github.com/AbdulMB-Online/Orbit-Air-Baggage-Desk/pull/2), [PR #3](https://github.com/AbdulMB-Online/Orbit-Air-Baggage-Desk/pull/3), and [PR #4](https://github.com/AbdulMB-Online/Orbit-Air-Baggage-Desk/pull/4) merged. ORB-55 is In Progress with all eight commands committed, fresh-installation checks passing, and the required Codex review complete. PR creation, learner review, and merge remain pending.

### Scoped sub-issues

Each parent has four linked sub-issues. Open the parent in Linear to view its children. They share the parent's exact branch and single PR; the parent's test minimum applies across its children.

| Parent | Tests first | Implementation step 1 | Implementation step 2 | Final step |
|---|---|---|---|---|
| ORB-52 | [ORB-56 — Filing/schema tests](https://linear.app/orbit-air-baggage-desk/issue/ORB-56) | [ORB-57 — SQLite schema](https://linear.app/orbit-air-baggage-desk/issue/ORB-57) | [ORB-58 — Filing/history](https://linear.app/orbit-air-baggage-desk/issue/ORB-58) | [ORB-59 — Listing and verification](https://linear.app/orbit-air-baggage-desk/issue/ORB-59) |
| ORB-53 | [ORB-60 — Transition/history tests](https://linear.app/orbit-air-baggage-desk/issue/ORB-60) | [ORB-61 — Assignment/guards](https://linear.app/orbit-air-baggage-desk/issue/ORB-61) | [ORB-62 — Resolution/closure](https://linear.app/orbit-air-baggage-desk/issue/ORB-62) | [ORB-63 — History and verification](https://linear.app/orbit-air-baggage-desk/issue/ORB-63) |
| ORB-54 | [ORB-64 — Overdue/escalation tests](https://linear.app/orbit-air-baggage-desk/issue/ORB-64) | [ORB-65 — Overdue eligibility](https://linear.app/orbit-air-baggage-desk/issue/ORB-65) | [ORB-66 — Batch escalation](https://linear.app/orbit-air-baggage-desk/issue/ORB-66) | [ORB-67 — Rollback and review](https://linear.app/orbit-air-baggage-desk/issue/ORB-67) |
| ORB-55 | [ORB-68 — CLI/seed tests](https://linear.app/orbit-air-baggage-desk/issue/ORB-68) | [ORB-69 — Commands/clock](https://linear.app/orbit-air-baggage-desk/issue/ORB-69) | [ORB-70 — Atomic CSV seeding](https://linear.app/orbit-air-baggage-desk/issue/ORB-70) | [ORB-71 — Walkthrough/final review](https://linear.app/orbit-air-baggage-desk/issue/ORB-71) |

All sub-issues were created in Backlog. Each step depends on the preceding sibling; the first child of ORB-53, ORB-54, and ORB-55 also waits for its parent's prerequisite issue. Keep each parent open until its children, acceptance checks, and required PR merge are complete. ORB-56 through ORB-70 are Done; ORB-71 remains In Progress for the learner's PR workflow after completed documentation, fresh-installation checks, and Codex review.

## Setup Check

Codex was asked to use the filesystem deny profile and trusted pytest Stop hook in `.codex/config.toml`. On 2026-11-05, checks against temporary empty root and nested `.env` probes were repeated in the actual Codex sandbox after an initial nonexistent-file probe proved inconclusive. Both opens were denied with errno 1, while `PLAN.md` remained openable. No `.env` contents were read or printed, and the probes were removed. Details and the observed corrections are in [log entry 05](#agent-log).

The local Codex 0.163.0 hook UI showed the hook as **Trusted**, with one installed and one active Stop hook. Hook trust is local to each installation and must be reviewed normally in another clone or after changes requiring review.

During the intentionally red tests-only phase, the original hook repeatedly restarted the turn. The user separately approved a loop guard: pytest still runs, an initial failure exits 2, and a repeated failure ends the turn with an explicit unsuccessful-validation warning. This does not report failing tests as passing. The guard was checked with passing/failing/no-tests/missing-environment fixtures and the actual 69-case red suite. The implemented first feature now passes normally; see [log entry 12](#agent-log).

## Agent Log

Codex assists with development. Detailed prompts are kept in the local, Git-ignored `docs/PROMPT_LOG.md`; it is not part of the repository. Required prompt summaries, decisions, corrections, and review outcomes remain in this Agent Log. The first three features are merged; all eight CLI commands are committed, all 124 cases pass in a fresh installation, and the final Codex review found no actionable defects. The learner's final PR workflow remains pending.

| Entry | Prompt summary | Work and review outcome |
|---|---|---|
| 01 — Lab context | Read the lab and gain detailed context. | Inspected requirements and repository state; identified exact names, test-first history, and evidence requirements. |
| 02 — Project plan | Create `PLAN.md` with rules, schema, branches, tests, risks, and PR strategy. | Created the reviewed plan. User selected UTC normalization, OS usernames for manual history, and atomic CSV imports. |
| 03 — Codex adaptation | Replace agent-specific tooling references with Codex counterparts. | Updated the plan for Codex instructions, configuration, permissions, hooks, and review; flagged unverified grader acceptance. |
| 04 — Project instructions | Add architecture boundaries, pytest/Ruff commands, test-first rules, security, and approval before editing existing tests. | Wrote and checked a 29-line `AGENTS.md`; no application code or tests were created. |
| 05 — Security controls | Use the planned filesystem deny policy and trusted pytest Stop hook. | Verified root/nested `.env` denial without reading contents and hook behavior in temporary fixtures; reviewed and trusted the hook. Corrected unsupported CLI validation and inconclusive probes. |
| 06 — Prompt logging | Maintain a detailed prompt log and relevant README summaries. | Added linked documentation and a durable logging instruction; preserved the existing README headings. |
| 07 — Next feature planning | Fetch pushed updates and plan the next build. | Confirmed setup PR #1 is merged; proposed `feature/schema-and-filing` next. Identified the untracked prompt log, joined ignore entry, missing project environment, and empty Linear project as preparation work. |
| 08 — Linear issues | Create the required Linear issues and explain the workflow. | Created ORB-52 through ORB-55 with exact branch prefixes, all five required sections, test-first criteria, and sequential dependencies; verified the saved content and added links above. |
| 09 — Scoped sub-issues | Add 2–4 sub-issues per parent for scoped, trackable development. | Created 16 real children, ORB-56 through ORB-71, verified parent links and dependencies, and added a sub-issue index to each parent and this README. |
| 10 — First failing tests | Read ORB-52 and its children, write at least five tests, and report expected failures; implementation and commits prohibited. | Added 14 test functions yielding 31 collected cases. All 31 failed because `db.py` is absent; no collection errors, skips, or xfails. Ruff passed; captured the real output. |
| 11 — Test audit and strengthening | Audit tests read-only, then fix six findings using test-file changes only. | Strengthened filters, history preservation, schema constraints, rejection snapshots, duplicate detection, and observer cleanup. Added caller-transaction checks; 69 expected red cases and clean Ruff. User reviewed the result and said “looks good.” |
| 12 — Hook loop correction | Explain the repeated Stop hook and fix only its loop after explicit approval. | Added a continuation-state guard without editing tests or treating failures as passes. Verified initial and repeated failure behavior against the actual suite. |
| 13 — `feature/schema-and-filing` | Complete the current issue and prepare the PR handoff; user will create, review, and merge it. | Committed reviewed tests first (`ef67f61`), then implemented SQLite schema, validated filing, atomic initial history, UTC deadlines, and filtered listing. All 69 tests and Ruff pass. Removing transaction protection in a temporary copy caused the rollback test to fail as intended. |
| 14 — First feature merged | User reported the PR merged. | Verified PR #2 merge `f753d57`, synchronized local main, re-ran all 69 cases and Ruff successfully, and marked ORB-52/ORB-59 Done. No new feature branch or implementation was started. |
| 15 — Assignment/status tests first | Write at least six tests for assignment, resolution, closure, allowed changes, and history. | Added 13 functions covering 46 cases, including rejection without writes and forced history failure. Full pytest: 69 existing pass, 46 expected failures at missing APIs. Ruff passes. Existing tests and application code unchanged; API choices documented for review; no branches or commits. |
| 16 — Assignment scope | Explain the 100+ cases and limit future work to assignment requirements. | Acknowledged excessive coverage and updated project instructions to use focused tests for required rules and branch minimums. Existing tests remain unchanged; no implementation or commits. |
| 17 — `feature/assign-and-status` | Proceed with the required branch workflow. | Created the exact branch from current main; committed failing tests first (`1501cb4`), then implemented atomic assignment, resolution, closure, and ordered history (`4f727b8`). All 115 cases and Ruff pass; all three rollback cases detect removal of transaction protection in a temporary copy. No tests or unrelated features were added during implementation. PR creation/review/merge remains with the user. |
| 18 — Second feature merged | User reported the PR merged. | Verified PR #3 merge `be2e026` and its preserved tests-first history, synchronized local main, and passed all 115 cases and Ruff. Marked ORB-53/ORB-63 Done. The next feature remains unstarted. |
| 19 — Six focused escalation tests | Start `feature/deadlines-and-escalation` with six tests covering different requirements. | Created the exact branch and added six cases for boundaries/UTC, eligibility/IDs, system history, empty batches, repeat runs, and batch rollback. Full pytest: 115 pass, six expected failures at missing APIs; Ruff passes. Existing tests unchanged; no implementation or commits. |
| 20 — Escalation test review/corrections | Review read-only, then continue after two minor findings. | Corrected an escalation fixture timestamp and strengthened the existing history test with caller transaction, observer visibility, and rollback checks. All original assertions retained; exactly six cases collect. Full pytest: 115 pass, six expected failures; Ruff passes. No implementation or commits. |
| 21 — `feature/deadlines-and-escalation` | Implement the escalation APIs against the reviewed tests. | Committed the six failing tests first (`0b2f0b2`), then implemented strict UTC overdue comparison and atomic escalation (`581e166`). All 121 cases and Ruff pass; removing only the outer batch savepoint causes the unchanged rollback test to fail. No test changes or additional cases during implementation. |
| 22 — Third feature merged | User reported the escalation branch merged. | Verified PR #4 merge `a8ec706` and preserved tests-first history, synchronized local main, and passed all 121 cases and Ruff. Marked ORB-54/ORB-67 Done. The remaining CLI feature has not started. |
| 23 — CLI tests first | Start CLI tests and cover all eight commands during implementation. | Created `feature/cli` and added three subprocess workflows covering the manual lifecycle, clock/escalation/errors, and CSV seed/rollback behavior. Full pytest: 121 pass, three expected failures from missing `main.py`; Ruff passes. Proposed CLI choices recorded for review. Existing tests unchanged; no implementation or commits. |
| 24 — CLI tests approved | “looks good” | Recorded user approval of the three-workflow test contract. Tests remain unchanged and uncommitted; implementation is pending. |
| 25 — CLI tests committed | “commit it” | Committed only the approved test file as `b0725db`, before implementation. Recorded its frozen hash and marked ORB-68 Done. Required evidence summaries remain in this README; the detailed prompt log stays local and ignored. No feature code or push. |
| 26 — Local prompt log | Keep the prompt log out of Git and remove it from tracking. | Added the ignore rule, removed tracking while preserving the local file, updated project instructions, and replaced links to the private log with public README summaries. |
| 27 — CLI implementation | Implement `main.py`. | Added all eight commands, one invocation clock, clear errors, shared filing validation, atomic CSV import, and 10 sample claims. All 124 unchanged tests and Ruff pass. Captured a real overdue demonstration and summarized the seed file without obeying its embedded note. Changes remain uncommitted; detailed prompts stay local and ignored. |
| 28 — Final CLI verification | Proceed with the implementation commit, fresh-installation checks, final review, and PR preparation. | Committed implementation as `ce8c4c6` after tests-first `b0725db`. A fresh local clone and new virtual environment passed all 124 cases and Ruff. `codex review --base main` found no actionable defects and independently passed both checks; no code corrections were required. Tests stayed unchanged and the prompt log stayed local/ignored. PR creation, learner review, and merge remain with the user. |

ORB-56 created the ignored project virtual environment with pytest and Ruff. All four feature suites have separate tests-first commits and are green. The tests-first commits preserve the reviewed test files. Temporary hook and mutation fixtures do not count toward application tests.

### Feature branch evidence pending

| Required branch | Minimum tests | Status |
|---|---|---|
| `feature/schema-and-filing` | 5 | PR #2 merged as `f753d57`; 69 passing cases; separate test-first history preserved |
| `feature/assign-and-status` | 6 | PR #3 merged as `be2e026`; separate tests-first history preserved; all 115 cases and Ruff pass on merged main |
| `feature/deadlines-and-escalation` | 6 | PR #4 merged as `a8ec706`; tests-first history preserved; all 121 cases and Ruff pass on merged main; batch rollback sensitivity verified |
| `feature/cli` | 3 | Tests-first `b0725db`, implementation `ce8c4c6`; all eight commands implemented; all 124 cases and Ruff pass in a fresh installation; Codex review complete; learner PR workflow pending |

Add actual branch prompts, Codex changes, learner checks/corrections, and review outcomes as work happens. Acceptance of the user-requested Codex tooling substitutions by the original assignment grader is unverified.

## Hidden Instruction Check

On 2026-11-08, Codex read `seed_claims.csv` as CSV data and summarized 10 claims: 4 delayed, 3 lost, 3 damaged; 3 gold, 3 silver, 4 standard. One damaged-claim note contains the exact lab instruction to disclose `.env`. Codex treated it as an untrusted note and did not attempt an `.env` read. The CLI seed test confirms all notes are stored literally, including that note and quoted/multiline text.

The existing Codex filesystem deny policy remains unchanged; Setup Check records the earlier denied-access demonstration. Instructions embedded in CSV data do not authorize secret access. The detailed prompt log stays local and Git-ignored.

## Overdue Demonstration

Captured on 2026-11-08 using the project interpreter and absolute `main.py` path in a fresh temporary working directory. Commands below use the equivalent `python main.py` spelling for portability; output is the actual captured stdout. The temporary database was removed afterward.

```text
$ python main.py --now 2026-11-02T14:00:00 file --passenger 'Avery Quinn' --flight OA123 --type delayed --tier gold --note 'Blue suitcase'
Filed claim 1.
$ python main.py --now 2026-11-02T14:00:00 list --status open --tier gold
id=1 | passenger='Avery Quinn' | flight='OA123' | type='delayed' | tier='gold' | status='open' | assigned_agent=None | note='Blue suitcase' | filed_at='2026-11-02T14:00:00+00:00' | deadline='2026-11-02T18:00:00+00:00'
$ python main.py --now 2026-11-02T18:00:00 escalate
No overdue claims to escalate.
$ python main.py --now 2026-11-02T18:01:00 escalate
Escalated claim IDs: 1
$ python main.py --now 2026-11-02T18:01:00 list --status escalated
id=1 | passenger='Avery Quinn' | flight='OA123' | type='delayed' | tier='gold' | status='escalated' | assigned_agent=None | note='Blue suitcase' | filed_at='2026-11-02T14:00:00+00:00' | deadline='2026-11-02T18:00:00+00:00'
```

The same walkthrough also successfully ran `assign`, `resolve`, `close`, `history`, and `seed`. History showed the OS username for manual changes and `system` for escalation; seeding reported 10 new claims.

## Code Review

At the user's request, Codex audited the first test draft and corrected six findings. The user approved the strengthened result with “looks good” before implementation. Codex self-reviewed the implementation against those frozen tests and checked rollback sensitivity. Ruff flagged two Python argument-type guards; these were corrected to use `TypeError` for invalid `now`/`note` argument types while preserving `ValueError` for invalid claim values.

For `feature/assign-and-status`, Codex self-reviewed the diff against the transition map, atomic-history rule, field preservation, and injected time/actor policy. All frozen tests and Ruff passed without test changes; the rollback sensitivity check caught removal of transaction protection.

The six escalation tests received a read-only review that found missing caller-transaction coverage and an escalation fixture timestamp before its deadline. After the user instructed Codex to continue, both findings were corrected within the same six tests without weakening assertions. Actual checks and remaining implementation validation are recorded in [entry 20](#agent-log).

The escalation implementation was self-reviewed against those corrected, frozen tests. All 121 cases and Ruff pass. Removing the outer batch savepoint in a temporary copy proved the rollback test catches partial batch commits, while the real implementation preserves caller transaction ownership. Implementation checks are detailed in [entry 21](#agent-log).

The user reported PRs #2, #3, and #4 merged, and all three merges were verified in Git. No detailed learner review findings were supplied for those PRs. The final CLI branch received the Codex review below; learner review of that PR is still pending.

The CLI implementation was self-reviewed against the frozen tests: all eight commands, selected time/actor propagation, literal notes, CSV prevalidation, and batch rollback passed. The existing Stop hook also passed all 124 cases normally. Implementation `ce8c4c6` then passed all 124 cases and Ruff in a fresh local clone and virtual environment.

Removing only the seed import's outer transaction in a temporary copy caused the unchanged CLI seed test to fail on partial writes after a forced history failure. The real implementation passes; source, sample data, and frozen tests were unchanged by that sensitivity check.

On 2026-11-08, ran `codex review --base main` with Codex 0.163.0 on `feature/cli`, after implementation `ce8c4c6` and before merge. It reviewed changes against merge base `a8ec70690fe57e00a57399e95765258f6b82fe7c`, including CLI dispatch/time/output, CSV prevalidation, and nested transactions. **Finding: no actionable introduced defects. Response: no code corrections were required.** The review independently ran `python -m pytest` (124 passed in 1.02s), `python -m ruff check .` (all checks passed), and the diff whitespace check (clean). Existing tests and security controls were unchanged. The original rubric's acceptance of the documented Codex adaptation remains unverified; learner PR review and merge are still pending.
