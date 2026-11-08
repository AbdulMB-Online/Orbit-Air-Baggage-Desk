#!/bin/sh
# Keep stdout reserved for the Codex Stop hook JSON response.
set -u

project_root=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd -P) || {
    printf '%s\n' 'Cannot locate the project root for the pytest Stop hook.' >&2
    exit 2
}
project_python="$project_root/.venv/bin/python"

hook_continued=$(python3 -c '
import json
import sys

try:
    event = json.load(sys.stdin)
    if not isinstance(event, dict):
        raise ValueError("Expected an event object")
    active = event.get("stop_hook_active", False)
    if not isinstance(active, bool):
        raise ValueError("Expected a boolean stop_hook_active")
except (ValueError, TypeError):
    print("Invalid Stop hook input; expected JSON with a boolean stop_hook_active.", file=sys.stderr)
    sys.exit(2)

print("true" if active else "false")
') || exit 2

if [ ! -x "$project_python" ]; then
    printf '%s\n' \
        'pytest Stop hook blocked: .venv/bin/python is missing.' \
        'Set up the project virtual environment with pytest, then rerun the suite.' >&2
    pytest_status=127
else
    cd "$project_root" || exit 2
    "$project_python" -m pytest </dev/null >&2
    pytest_status=$?
fi

if [ "$pytest_status" -ne 0 ]; then
    printf 'pytest Stop hook: pytest has not passed (status %s).\n' "$pytest_status" >&2
    if [ "$hook_continued" = "true" ]; then
        printf '{"continue":false,"stopReason":"Stopping after one unsuccessful pytest continuation.","systemMessage":"Pytest has not passed (status %s). Ending this turn to prevent a retry loop; existing scope restrictions still apply."}\n' "$pytest_status"
        exit 0
    fi
    printf '%s\n' \
        'Review the reported failure within the authorized scope; no collected tests is not a passing suite.' \
        'Do not modify existing tests or expand the task scope without user approval.' >&2
    exit 2
fi

printf '{}\n'
