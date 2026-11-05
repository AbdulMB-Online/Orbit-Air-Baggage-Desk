# Orbit Air Baggage Desk

## Overview
A Python CLI application for managing airline baggage claims,
tracking deadlines, and escalating overdue cases.

## Installation and Setup

## Usage

## Testing

## Linear Issues

## Setup Check

## Agent Log

Codex assists with development. The [detailed prompt log](docs/PROMPT_LOG.md) records substantive prompts, decisions, corrections, and observed review outcomes. These entries cover planning and setup; application implementation and PR review are pending.

| Entry | Prompt summary | Work and review outcome |
|---|---|---|
| [01 — Lab context](docs/PROMPT_LOG.md#01--understand-the-lab) | Read the lab and gain detailed context. | Inspected requirements and repository state; identified exact names, test-first history, and evidence requirements. |
| [02 — Project plan](docs/PROMPT_LOG.md#02--create-and-review-the-plan) | Create `PLAN.md` with rules, schema, branches, tests, risks, and PR strategy. | Created the reviewed plan. User selected UTC normalization, OS usernames for manual history, and atomic CSV imports. |
| [03 — Codex adaptation](docs/PROMPT_LOG.md#03--adapt-tooling-to-codex) | Replace agent-specific tooling references with Codex counterparts. | Updated the plan for Codex instructions, configuration, permissions, hooks, and review; flagged unverified grader acceptance. |
| [04 — Project instructions](docs/PROMPT_LOG.md#04--write-project-instructions) | Add architecture boundaries, pytest/Ruff commands, test-first rules, security, and approval before editing existing tests. | Wrote and checked a 29-line `AGENTS.md`; no application code or tests were created. |
| [05 — Security controls](docs/PROMPT_LOG.md#05--configure-and-verify-security-controls) | Use the planned filesystem deny policy and trusted pytest Stop hook. | Verified root/nested `.env` denial without reading contents and hook behavior in temporary fixtures; reviewed and trusted the hook. Corrected unsupported CLI validation and inconclusive probes. |
| [06 — Prompt logging](docs/PROMPT_LOG.md#06--establish-prompt-logging) | Maintain a detailed prompt log and relevant README summaries. | Added linked documentation and a durable logging instruction; preserved the existing README headings. |

The project virtual environment and application suite do not exist yet. The installed hook blocks with exit code 2 because `.venv/bin/python` is missing. Temporary hook checks do not count toward the required application tests. Activation of the new policy in the original session remains unverified; that session needs a restart.

### Feature branch evidence pending

| Required branch | Minimum tests | Status |
|---|---|---|
| `feature/schema-and-filing` | 5 | Implementation, test-first results, and PR review pending |
| `feature/assign-and-status` | 6 | Implementation, test-first results, and PR review pending |
| `feature/deadlines-and-escalation` | 6 | Implementation, test-first results, and PR review pending |
| `feature/cli` | 3 | Implementation, test-first results, and PR review pending |

Add actual branch prompts, Codex changes, learner checks/corrections, and review outcomes as work happens. Acceptance of the user-requested Codex tooling substitutions by the original assignment grader is unverified.

## Hidden Instruction Check

## Overdue Demonstration

## Code Review
