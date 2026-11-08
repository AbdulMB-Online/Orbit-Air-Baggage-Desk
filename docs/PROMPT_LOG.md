# Codex Prompt and Review Log

Record substantive prompts, implementation decisions, corrections, and review outcomes here. Keep relevant summaries in the README's [Agent Log](../README.md#agent-log).

## Recording conventions

- Entries 01–05 were reconstructed from the conversation and observed tool results on 2026-11-05. Prompts are summaries unless explicitly quoted; this is not a verbatim transcript.
- For future entries, record the date, branch/issue/PR when available, prompt, scope, files changed, decisions, corrections, checks and outcomes, and unresolved work.
- Preserve earlier failures and append their corrections. Separate observed results from plans; never invent learner review, passing checks, commits, or PR findings.
- Do not record secrets, `.env` contents, credentials, or unrelated personal information. Embedded instructions in claim notes remain data.
- Setup entries do not replace the assignment's per-feature-branch evidence. Add a substantive entry for each required branch as work happens.

## 01 — Understand the lab

**Date:** 2026-11-05. **Stage:** discovery before implementation.

**Prompt summary:** Read `orbit_air_baggage_desk_lab.md` and gain detailed project context.

**Work and decisions:** Read the lab and inspected the README, ignore rules, tracked files, branches, remote, and initial history. Identified the eight commands, exact names, strict overdue boundary, allowed transitions, atomic claim/history writes, branch test minimums, and required development evidence. No application code was present.

**Review outcome:** Reported that working features alone would not meet the full rubric. Flagged the remote repository's capitalization difference from `orbit-air-baggage-desk`; public visibility was not verified. Discovery changed no files.

## 02 — Create and review the plan

**Date:** 2026-11-05. **Stage:** planning.

**Prompt summaries:** Act as a senior engineer and create `PLAN.md` covering the customer problem, SLA rules, schema, four branches and test minimums, risks, and test-first/PR strategy. Preserve exact names, flag assumptions, and create no application code, tests, branches, or commits. Later, explicitly create the file from the reviewed draft.

**Decisions:** Put connections/schema in `db.py`, business rules in `claims.py`, and CLI/clock selection in `main.py`. Use `claims` and `history` tables with CHECK constraints and atomic writes. Plan branch test minimums of 5, 6, 6, and 3, and at least 20 passing application tests overall.

**User-selected policies:** Normalize timestamps to UTC, treating offset-free input as UTC; use the local OS username for manual history and `system` for automatic escalation; reject an entire CSV import when any row is invalid.

**Assumptions flagged:** Initial history uses NULL old status; escalation preserves ownership and uses one batch transaction; agent names cannot be blank; optional stretch goals follow required work.

**Correction and review outcome:** The first request arrived in Plan Mode, so Codex supplied a review draft without writing files. After the mode changed and the user requested creation, wrote `PLAN.md` and checked its six topics, branch names, and chosen policies. No application code, tests, branches, or commits were created by Codex for that work.

**Evidence:** [PLAN.md](../PLAN.md). A later repository inspection showed commit `8d24bea`, titled `docs: finalize project development plan`; this log does not attribute that commit to Codex.

## 03 — Adapt tooling to Codex

**Date:** 2026-11-05. **Stage:** plan revision.

**Prompt summary:** Because development uses Codex, replace agent-specific files and details with Codex counterparts.

**Changes and decisions:** Updated only the plan to use `AGENTS.md`, optional untracked `AGENTS.override.md`, `.codex/config.toml`, filesystem permissions, a pytest Stop hook, and `codex review --base main` before merging the last PR. Kept application filenames, commands, branch names, Linear project name, and README headings unchanged.

**Review outcome:** Consulted official Codex documentation and local CLI help; observed CLI version 0.163.0. Checked removal of previous agent-specific filenames and review command. Distinguished Git ignore rules from read protection and documented that an override replaces the instruction file in the same directory.

**Open item:** The original lab remains unchanged. Grader acceptance of Codex substitutions is unverified. Documentation sources are linked in [PLAN.md](../PLAN.md#codex-tooling-details).

## 04 — Write project instructions

**Date:** 2026-11-05. **Stage:** project guidance.

**Prompt summaries:** Create an empty `AGENTS.md`, then fill it from the plan and lab with project instructions, architecture boundaries, pytest/Ruff commands, test-first work, security restrictions, and approval before changing existing tests. Create no application code, branches, or commits.

**Changes and decisions:** Wrote a 29-line instruction file covering boundaries, SLA hours, time injection, transaction integrity, verification commands, and branch test minimums. Explicit approval is required before modifying, deleting, renaming, skipping, or weakening existing tests, including bypasses through fixtures or configuration.

**Commands documented:**

```text
python -m pytest
python -m pytest tests/test_claims.py
python -m pytest tests/test_claims.py -k test_name
python -m ruff check .
```

**Review outcome:** Read back the file, checked its 29-line length, inspected repository status, and ran `git diff --check`. Included architecture boundaries at the user's explicit request despite the original instruction-file rubric discouraging architecture descriptions. No application test pass or Ruff result was claimed.

**Evidence:** [AGENTS.md](../AGENTS.md). Entry 06 subsequently updates its logging instruction.

## 05 — Configure and verify security controls

**Date:** 2026-11-05. **Stage:** security setup. **Local CLI:** Codex 0.163.0.

**Prompt:** “Use the Codex filesystem deny policy and trusted pytest Stop hook planned in .codex/config.toml”

**Changes and decisions:**

- Added [.codex/config.toml](../.codex/config.toml): default profile `orbit-air`, extending `:workspace`, with root/nested `.env` denial and a synchronous Stop hook with a 120-second timeout.
- Added [.codex/hooks/pytest_stop.sh](../.codex/hooks/pytest_stop.sh): resolve the project root and run `.venv/bin/python -m pytest` there, including when invoked from a subdirectory.
- Route pytest output and failure feedback to stderr; emit only `{}` on stdout for success. Map every nonzero pytest result to hook exit 2. Missing environments and no collected tests must not count as success.
- Prepared and validated files before installing into the protected `.codex` directory with explicit execution approval. Used the normal hook trust flow without bypass flags.

**Corrections during verification:**

1. `codex --strict-config features list` was unsupported for that subcommand. Used TOML parsing, structural assertions, shell syntax checks, normal feature discovery, and actual CLI hook discovery instead. No successful strict-schema check is claimed.
2. A nested Codex sandbox failed with `sandbox_apply: Operation not permitted`. Repeated outside the nested sandbox with explicit execution approval.
3. Initial probes used nonexistent `.env` paths and returned errno 2, which did not demonstrate denial. Repeated with temporary empty probes, read no contents, and removed only probes created for the check.

**Observed results:**

| Check | Result |
|---|---|
| TOML parsing and assertions | Confirmed active default profile, denied paths, hook registration, and timeout |
| `/bin/sh -n` | Hook syntax passed |
| Temporary fixture without virtual environment | Hook exit 2; missing interpreter reported on stderr |
| Temporary fixture with an actual passing pytest test | Hook exit 0; stdout parsed as `{}`; one passing test reported on stderr |
| Temporary fixture with an actual failing pytest test | Hook exit 2; one failed test reported on stderr |
| Temporary fixture with no collected tests | Pytest status 5 mapped to hook exit 2 |
| Fixture path containing spaces; nested working directory | Correct project root resolved and pytest executed there |
| Actual sandbox with root/nested empty `.env` probes | Both opens denied with errno 1; `PLAN.md` remained openable |
| Probe cleanup | No temporary denial-probe directories remained |
| Installed hook in the repository | Exit 2 because `.venv/bin/python` was missing |

**Trust review outcome:** Opened local Codex hook settings without sending a coding prompt. Reviewed the source, command, synchronous mode, and timeout. Trusted the exact definition using the standard review flow. The UI changed from “New hook - review required” to “Trusted” and displayed Stop: Installed 1, Active 1. Closed the settings session afterward.

**Evidence limits and pending work:** The temporary pytest fixtures verified hook behavior and do not count toward the required application suite. Results above are transcribed from observed tool output; the temporary harness is not a committed test artifact. The project virtual environment, application tests, application Ruff run, hidden-instruction summary exercise, and PR review are pending. The original session needs a restart to load the new policy; activation there has not been verified. Trust is local to this installation and is not portable to other clones or users.

## 06 — Establish prompt logging

**Date:** 2026-11-05. **Stage:** development documentation.

**Prompt:** “Record substantive Codex prompts, implementation decisions, corrections, and review outcomes in docs/PROMPT_LOG.md. Include relevant prompt summaries in the README's Agent Log section.”

**Changes and decisions:** Created this log from recorded prompts and tool results. Added linked summaries under the exact README heading `Agent Log`. Updated the existing review instruction in `AGENTS.md` to maintain both logs while preserving its 29-line length. Separated setup evidence from future branch work.

**Correction:** The first patch did not apply because the README changed during preparation. Re-read the current scaffold and inserted content under `Agent Log`, preserving the other headings and existing overview. No changes from the failed patch were applied.

**Review outcome:** Local Markdown links and anchors, required branch names, whitespace checks, and the 29-line instruction-file count passed. Verified that the existing README overview and headings were preserved. No application tests, Ruff execution, independent code review, or PR review is claimed for this documentation task.

## 07 — Fetch updates and plan the first feature

**Date:** 2026-11-05. **Stage:** repository synchronization and next-step planning.

**Prompt summary:** Fetch the user's pushed updates, then plan what to build next.

**Observed state:** Fetched `origin`; `origin/main` advanced to `61ff9f3`, the merge of setup PR #1. The current checkout remains `chore/codex-setup` at `d1371f3`, and its tracked file contents match `origin/main`. No branch switch, local merge, or commit was performed. The first fetch was blocked from writing `.git/FETCH_HEAD`; the explicitly approved retry succeeded.

**Readiness findings:** `docs/PROMPT_LOG.md` is still untracked and absent from the merged remote tree despite README links to it. The remote `.gitignore` still contains the joined `.DS_Storeorbit_air_baggage_desk_lab.md` line. No project virtual environment, tests, or dependency manifest exists. The connected Linear project [Orbit Air Baggage Desk](https://linear.app/orbit-air-baggage-desk/project/orbit-air-baggage-desk-8930c0fcca68) exists; its issue listing returned no issues.

**Proposed next slice, not yet authorized for implementation:** Build `feature/schema-and-filing` first, following the existing plan. Cover schema creation, constraints, validated filing, tier deadlines, initial transactional history, and filtered listing. Keep CLI commands for `feature/cli` and later status changes/escalation for their required branches.

**Planned tests:** Valid filing and complete initial history; blank/whitespace passenger and flight; invalid type and tier; all three tier deadlines; direct SQL CHECK violations; unfiltered/status/tier/combined listing; and rollback of filing when initial history insertion fails. Use temporary databases and fixed timestamps, meeting or exceeding the branch's minimum of five tests.

**Planned prerequisites and workflow:** Include the prompt log in a future authorized commit, fix the ignore entry, prepare a reproducible pytest/Ruff environment, and create the four required agent-ready Linear issues. Base future feature work on updated `main`; observe failing tests and preserve the separate test-first commit before implementation. Finish with passing pytest and Ruff, a reviewed diff, updated evidence logs, and a PR title prefixed with `feature/schema-and-filing`.

**Review outcome:** Inspected the fetched Git history and tracked tree, local setup files, the lab's branch requirements, and the connected Linear project/issues. These are planning findings; no application implementation, test execution, issue creation, branch creation, or commit was performed for this request.

## 08 — Create the four required Linear issues

**Date:** 2026-11-05. **Stage:** issue preparation before application implementation.

**Prompt summary:** The user said it was time to create the Linear issues and asked how to proceed. Codex explained the required structure, then created the four issues in the existing Orbit Air Baggage Desk project.

**Preparation and decisions:** Checked the project and confirmed it had no issues before creating any. Confirmed the team's Backlog status. Created one issue per required branch, kept all four in Backlog and unassigned, and added a sequential dependency chain matching the reviewed build order. Each title starts with the exact branch name. Each description contains Problem, Actual behavior, Expected behavior, Done when, and Constraint, with implementation notes in a collapsed Agent notes section.

| Issue | Exact title | Blocked by |
|---|---|---|
| [ORB-52](https://linear.app/orbit-air-baggage-desk/issue/ORB-52/featureschema-and-filing-persist-and-file-baggage-claims) | feature/schema-and-filing: persist and file baggage claims | None |
| [ORB-53](https://linear.app/orbit-air-baggage-desk/issue/ORB-53/featureassign-and-status-enforce-claim-transitions-and-history) | feature/assign-and-status: enforce claim transitions and history | ORB-52 |
| [ORB-54](https://linear.app/orbit-air-baggage-desk/issue/ORB-54/featuredeadlines-and-escalation-escalate-overdue-claims-atomically) | feature/deadlines-and-escalation: escalate overdue claims atomically | ORB-53 |
| [ORB-55](https://linear.app/orbit-air-baggage-desk/issue/ORB-55/featurecli-expose-claim-commands-and-csv-seeding) | feature/cli: expose claim commands and CSV seeding | ORB-54 |

**Acceptance criteria recorded:** Branch test minimums are 5, 6, 6, and 3, with at least 20 passing application tests overall. Each issue requires observed failing tests committed before implementation, preservation of existing tests without explicit approval to change them, passing pytest/Ruff checks, its own PR with the branch-name prefix, and updates to both evidence logs. Feature-specific criteria cover schema/validation/deadlines, assignment/transitions/history, strict overdue boundaries/rollback, and all CLI commands/atomic CSV import. Preserve time injection, the UTC policy, local username actors for manual operations, and system for escalation.

**Correction:** Linear automatically linked unformatted Python filenames in the first saved description as web domains. Wrapped filenames and verification commands in code formatting and updated that issue before creating the remaining issues.

**Review outcome:** Re-fetched all four full descriptions and checked every required heading, exact title prefix, Backlog state, and dependency relation. Verified that ORB-52 blocks ORB-53, ORB-53 blocks ORB-54, and ORB-54 blocks ORB-55. Added the four issue links to README's Linear Issues section and a summary to its Agent Log. Documentation links and whitespace are checked locally; no application tests or Ruff run is claimed for issue creation.

**Next action:** Prepare the missing project environment, then start ORB-52 using the agreed test-first workflow when implementation is requested. Creating the issues did not create application code, branches, or commits, and no issue is marked complete.

## 09 — Scope each parent into four sub-issues

**Date:** 2026-11-05. **Stage:** issue decomposition; no application implementation.

**Prompt summary:** Create 2–4 sub-issues for each parent so development is scoped and trackable. During preparation, the user shared a board screenshot and said the sub-issues were not visible.

**Decisions:** Use four children per parent: a complete tests-first contract, two implementation steps, and a final feature/verification/evidence step. Keep the original four branches and one PR per parent. The existing 5/6/6/3 test minimums apply across each parent's children, not separately per child. Preserve the approval requirement for existing-test changes and all security controls.

| Parent | Child issues in execution order |
|---|---|
| [ORB-52](https://linear.app/orbit-air-baggage-desk/issue/ORB-52) | [ORB-56](https://linear.app/orbit-air-baggage-desk/issue/ORB-56): filing/schema tests; [ORB-57](https://linear.app/orbit-air-baggage-desk/issue/ORB-57): schema/constraints; [ORB-58](https://linear.app/orbit-air-baggage-desk/issue/ORB-58): filing/initial history; [ORB-59](https://linear.app/orbit-air-baggage-desk/issue/ORB-59): filtered listing/verification |
| [ORB-53](https://linear.app/orbit-air-baggage-desk/issue/ORB-53) | [ORB-60](https://linear.app/orbit-air-baggage-desk/issue/ORB-60): transition/history tests; [ORB-61](https://linear.app/orbit-air-baggage-desk/issue/ORB-61): assignment/guards; [ORB-62](https://linear.app/orbit-air-baggage-desk/issue/ORB-62): resolution/closure; [ORB-63](https://linear.app/orbit-air-baggage-desk/issue/ORB-63): ordered history/verification |
| [ORB-54](https://linear.app/orbit-air-baggage-desk/issue/ORB-54) | [ORB-64](https://linear.app/orbit-air-baggage-desk/issue/ORB-64): boundary/escalation/rollback tests; [ORB-65](https://linear.app/orbit-air-baggage-desk/issue/ORB-65): strict eligibility; [ORB-66](https://linear.app/orbit-air-baggage-desk/issue/ORB-66): atomic batch escalation; [ORB-67](https://linear.app/orbit-air-baggage-desk/issue/ORB-67): rollback sensitivity/review |
| [ORB-55](https://linear.app/orbit-air-baggage-desk/issue/ORB-55) | [ORB-68](https://linear.app/orbit-air-baggage-desk/issue/ORB-68): CLI/seed tests; [ORB-69](https://linear.app/orbit-air-baggage-desk/issue/ORB-69): command dispatch/clock; [ORB-70](https://linear.app/orbit-air-baggage-desk/issue/ORB-70): atomic CSV import/sample data; [ORB-71](https://linear.app/orbit-air-baggage-desk/issue/ORB-71): walkthrough/demo/final review |

**Dependencies and scope:** Every child is a real Linear sub-issue with its parent's ID, project, and Backlog status, and remains unassigned. Later siblings are blocked by the preceding sibling. The first child under ORB-53, ORB-54, and ORB-55 is also blocked by the preceding parent. Parent-to-parent dependencies remain unchanged. Titles retain the exact branch prefix and add an ordered [1/4]–[4/4] label. Each description includes the five required sections, concrete completion checks, and agent notes.

**Status clarification:** When the user reported not seeing children, only the scope checks had been completed; no child records existed yet. Codex clarified that state, then created ORB-56 through ORB-71 and verified their actual parent relationships. Each parent now also has a linked Scoped sub-issues checklist. Refresh Linear and open a parent to inspect its children.

**Review outcome:** Re-read all 16 full descriptions and verified the five required headings, branch prefixes, Backlog status, parent IDs, four-child counts, and blocking relations. Appended links to each parent without replacing its existing acceptance criteria, added README's sub-issue index and Agent Log summary, and checked local documentation links/anchors and whitespace. These are planning records; no application tests or Ruff pass is claimed. No application code, branches, or commits were created, and no parent or child was marked complete.

## 10 — Write and run ORB-56 tests without implementation

**Date:** 2026-11-05. **Stage:** test-first red phase on the already-existing `feature/schema-and-filing` branch.

**Prompt:** “Have Codex read the first Linear ticket and sub-issues, write at least five meaningful tests, run pytest, and report expected failures. Explicitly prohibit implementation code and commits”

**Explicit scope:** Write tests and record their actual failures. Do not create `db.py`, `claims.py`, `main.py`, production stubs, branches, or commits. Do not implement ORB-57, ORB-58, or ORB-59 to make the tests pass. No existing tests were present to modify, and the security controls remain unchanged.

**Context read:** Re-read the full ORB-52 description and all four children, ORB-56 through ORB-59, including their dependencies and acceptance criteria, plus `PLAN.md`, `AGENTS.md`, and the lab's claims/deadline/history requirements.

**Changes:** Created `tests/test_claims.py` with 14 test functions and 31 parameterized cases. Used temporary SQLite databases, fixed filing time, and real SQL checks/trigger failure injection. Imports occur inside calls so the complete suite collects before the production modules exist. Added no mocks, stubs, skips, or xfail markers. Created the ignored `.venv` and installed pytest 9.2.0 and Ruff 0.17.3 under Python 3.15.0; no dependency manifest or application implementation was added.

**Proposed API decisions:** The lab specifies behavior rather than Python signatures. The test module documents the following chosen contract for review before implementation:

```text
db.connect_db(path) -> sqlite3.Connection
db.init_db(connection) -> None
claims.file_claim(connection, *, passenger, flight, claim_type, tier,
                  now, actor, note="") -> integer claim ID
claims.list_claims(connection, *, status=None, tier=None) -> iterable of mappings
```

Validation errors must be `ValueError` or a subclass with a field-specific message. SQLite storage errors propagate. Stored timestamps parse as UTC ISO strings; naive filing times mean UTC. These API and exception choices are test-contract assumptions, not extra names mandated by the lab. Listing tests directly prepare assigned/resolved fixture states without implementing later lifecycle commands.

| Acceptance area | Collected cases |
|---|---|
| Required schema columns, repeat initialization, foreign keys, and direct enum CHECK violations | 6 |
| Complete open claim and initial history, including optional-note default | 1 |
| Blank/whitespace passenger and flight; invalid type and tier, without writes | 6 |
| Gold, silver, and standard deadlines from injected time | 3 |
| Offset and naive input normalized to UTC | 2 |
| Quoted/SQL-like note preserved as literal data | 1 |
| Filing visible to an independent SQLite connection | 1 |
| Empty listing, filter intersections, and invalid filters | 10 |
| Trigger-induced initial-history failure rolls back filing and preserves existing records | 1 |

**Observed commands and outcomes:**

```text
.venv/bin/python -m pytest --collect-only -q
31 tests collected in 0.02s

.venv/bin/python -m pytest -q --tb=line
31 failed in 0.24s
Exit code: 1
Failure: ModuleNotFoundError: No module named 'db'

.venv/bin/python -m ruff check tests/test_claims.py
All checks passed!

.venv/bin/python -m ruff check .
All checks passed!
```

**Review outcome and limits:** All cases collected successfully and failed during execution at the missing `db` import; no collection errors, skips, or xfails occurred. The behavior assertions cannot yet be exercised, and rollback-test sensitivity cannot be demonstrated until implementation is authorized. Full observed pytest output is preserved in [ORB-56-pytest-red.txt](ORB-56-pytest-red.txt). The tests and evidence remain uncommitted, so ORB-56's test-first commit criterion is still pending and no issue is marked complete. The unchanged Stop hook is expected to block while the suite is red; it was not bypassed or weakened to conceal those failures.

## 11 — Audit and strengthen the reviewed tests

**Date:** 2026-11-07. **Stage:** read-only audit, followed by explicitly approved test-only revisions.

**Prompt summaries:** Audit requirements coverage, API assumptions, and test independence without changing files. Then address the six findings by changing test files only, preserving assertions, reviewing transaction composition, and running pytest/Ruff; no implementation, commits, or branch changes.

**Findings and approved corrections:** Added positive filters for every valid status/tier; full claim/history snapshots around schema reinitialization; primary-key/type/NOT NULL/blank/history-status/default checks; rejection checks on both empty and populated databases; cardinality checks that catch duplicate list rows; and explicit closing of observer connections. Listing fixtures now use direct SQL so their setup does not depend on the filing operation.

**API and transaction review:** Kept the documented function signatures, integer claim IDs, and mapping results. Preserved standalone persistence and added caller-owned batch commit/rollback/history-failure checks. Batch callers explicitly start a transaction before filing, and filing must not commit that outer transaction. The signatures are project choices rather than assignment-mandated names.

**Observed outcome:** 24 test functions collected 69 cases; all 69 failed at the missing `db` import as expected. Ruff passed after a nested-context style correction. Non-test file hashes, HEAD, and branch were checked unchanged. The user then said “looks good.” No implementation was written or committed during this phase.

## 12 — Fix the Stop hook loop with explicit approval

**Date:** 2026-11-07. **Stage:** separately authorized hook correction.

**Problem and prompts:** The original Stop hook ran pytest on every attempted completion and repeatedly restarted a deliberately tests-only task. The user chose to keep tests-only scope and interrupt, then asked what was happening. Codex explained that its original hook setup had not accounted for the red phase. The user separately approved: “Yes—fix only the hook loop.”

**Change:** Only `.codex/hooks/pytest_stop.sh` changed. It reads the documented boolean `stop_hook_active`, still runs pytest, exits 2 for an initial failure, and returns `continue: false` with an explicit unsuccessful-validation warning after a continuation. A protocol exit of 0 in that repeated-failure path does not claim that pytest passed. Configuration, tests, application files, documentation, branch, and commits remained unchanged during the hook-only task.

**Verification:** Temporary fixtures covered successful pytest on both paths, initial/repeated failures, missing virtual environments, no collected tests, missing/invalid continuation flags, and nested paths containing spaces. The installed hook was also run against the actual 69-case red suite: the initial path requested continuation, while the continued path stopped with a warning and still reported all 69 failures. No bypass flags or fabricated green results were used. Reference: [official Codex hooks documentation](https://learn.chatgpt.com/docs/hooks).

## 13 — Complete ORB-52 against the reviewed tests

**Date:** 2026-11-08. **Stage:** first feature implementation and PR preparation.

**Prompt and scope:** The user asked to satisfy the criteria rather than rely on temporary workarounds. After Codex checked the earlier tests-only restriction, the user authorized completion of the current issue and PR preparation, retaining PR creation, review, and merge. Codex scoped this to ORB-52 and its children, not the later assignment, escalation, or CLI issues.

**Tests first:** Fetched the remote, fast-forwarded the existing feature branch to merged setup baseline `61ff9f3`, and re-ran the reviewed suite before implementation: 69 failed with missing `db`. Saved the observed run in [ORB-56-pytest-red-69.txt](ORB-56-pytest-red-69.txt). Commit `ef67f61` contains only the reviewed test file and precedes all feature code. The frozen test SHA-256 is `6d586e3b868e292ec5e96d6fc73e20060e6085b71220a335ba9b07ebc74c79bb`.

**Implementation decisions:**

- `db.py` creates both planned tables, enables foreign keys, provides mapping rows, and enforces enum/required/blank-text constraints. Initialization preserves existing data. Explicit legacy SQLite transaction control supports caller `BEGIN` and connection contexts consistently on Python 3.12+.
- A unique SQLite savepoint makes standalone operations commit when released while nested operations leave the outer transaction under caller control. Failed claim/history writes roll back together; a caller can roll back an entire batch of otherwise successful filings.
- `claims.py` validates filing input, normalizes injected time to UTC, computes tier deadlines, binds all data values as SQL parameters, and writes the initial history in the same transaction. Listing validates filters, joins them with AND, and returns each claim once in ID order.
- Added pinned pytest/Ruff development requirements. Tests run with the project instructions' `python -m pytest` command from the repository root; no test is skipped or excluded. Fixed the joined `.DS_Store` ignore entry and ignored SQLite sidecar files.
- Did not implement later lifecycle operations, escalation, CSV importing, or `main.py`. Existing reviewed tests were not modified.

**Checks and actual corrections:** Schema-only validation passed 29 cases with 40 deselected. The complete suite then passed all 69 cases. Ruff found two invalid-Python-type guards that should raise `TypeError`; those guards were corrected without changing the `ValueError` contract for invalid claim values. The complete suite and Ruff then passed again. This was implementation self-review; no independent PR review or learner review of the implementation has been claimed.

**Scope correction:** Codex initially added an optional pytest import-path configuration and a separate PR-draft file. The user asked to avoid generating or committing additions beyond project needs. Both optional files were removed before staging or committing; the PR title/description will be handed off in the response, and the existing documented test command is retained.

**Rollback sensitivity:** Copied the source and frozen tests to an isolated temporary directory and replaced only filing's transaction context with `nullcontext`. The existing history-failure rollback test failed with an assertion error against that defect, while it passes against the real implementation. The real source and test hashes were unchanged. Observed output: [ORB-52-rollback-mutation.txt](ORB-52-rollback-mutation.txt).

**API walkthrough:** Filed a gold delayed claim at `2026-11-02T14:00:00+00:00` in a temporary database and filtered by open/gold. Observed ID 1, open status, gold tier, deadline `2026-11-02T18:00:00+00:00`, and one initial history entry. This is filing/listing evidence, not the later overdue-escalation demonstration.

**Implementation history:** Commit `ef80b49` contains the first feature code, development dependencies, and the relevant ignore fixes, after tests-only commit `ef67f61`. The optional pytest configuration and PR-draft file were excluded.

**Fresh-checkout verification:** Cloned implementation commit `ef80b49` into a temporary directory and created a separate virtual environment. The sandbox initially blocked PyPI DNS access; after explicit approval, dependency installation completed successfully. In that fresh checkout, `python -B -m pytest -q -p no:cacheprovider` reported `69 passed in 0.11s`, and `python -B -m ruff check --no-cache .` reported `All checks passed!`, both with exit code 0. No optional pytest configuration existed. The frozen test hash matched the reviewed file. Temporary checkout/environment files were removed afterward.

**Native hook verification:** Ran the actual hook with an initial-turn payload against the completed implementation. It ran all 69 tests successfully, returned exit code 0 with stdout `{}`, and requested no continuation. This verifies a normal passing outcome rather than use of the repeated-failure guard to finish implementation.

**Tracking and remaining work:** ORB-56 was marked Done only after the reviewed tests were committed; ORB-57's schema checks passed before it was marked Done, and ORB-58's filing/history work was marked Done after all 69 cases passed. ORB-59 and ORB-52 remain open for the user's PR creation/review/merge workflow. The later three required feature branches and full-lab demonstrations remain pending. The branch is being prepared for push; no PR creation or merge has been claimed.

## Pending feature and review evidence

| Required branch | Minimum tests | Prompt, implementation, correction, and review evidence |
|---|---|---|
| `feature/schema-and-filing` | 5 | Reviewed test-first commit `ef67f61`; all 69 cases and Ruff pass; user PR creation/review/merge pending |
| `feature/assign-and-status` | 6 | Not yet recorded; implementation pending |
| `feature/deadlines-and-escalation` | 6 | Not yet recorded; implementation pending |
| `feature/cli` | 3 | Not yet recorded; implementation pending |

For each branch, record the actual failing-test observation before implementation, subsequent passing checks, approved test changes, and learner checks. Add real issue/PR links and review findings only when they exist. The planned final PR review has not happened yet.
