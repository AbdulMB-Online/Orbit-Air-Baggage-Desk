#!/bin/sh
# Keep stdout reserved for the Codex Stop hook JSON response.
set -u

project_root=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd -P) || {
    printf '%s\n' 'Cannot locate the project root for the pytest Stop hook.' >&2
    exit 2
}
project_python="$project_root/.venv/bin/python"

if [ ! -x "$project_python" ]; then
    printf '%s\n' \
        'pytest Stop hook blocked: .venv/bin/python is missing.' \
        'Set up the project virtual environment with pytest, then rerun the suite.' >&2
    exit 2
fi

cd "$project_root" || exit 2
"$project_python" -m pytest </dev/null >&2
pytest_status=$?

if [ "$pytest_status" -ne 0 ]; then
    printf 'pytest Stop hook blocked: pytest exited with status %s.\n' "$pytest_status" >&2
    printf '%s\n' \
        'Resolve the reported failure before finishing; no collected tests is not a passing suite.' \
        'Do not modify existing tests or expand the task scope without user approval.' >&2
    exit 2
fi

printf '{}\n'
