# STRETCH GOAL 1
"""Reject Codex apply_patch operations targeting the project's tests folder."""

import json
import sys
from pathlib import Path

PROTECTED = (Path(__file__).resolve().parents[2] / "tests").resolve()
PATH_HEADERS = (
    "*** Add File: ", "*** Update File: ",
    "*** Delete File: ", "*** Move to: ",
)


def main() -> int:
    try:
        event = json.load(sys.stdin)
        if not isinstance(event, dict):
            raise TypeError("expected an event object")
        tool_input = event.get("tool_input")
        if not isinstance(tool_input, dict):
            raise TypeError("expected tool_input")
        patch = tool_input.get("command")
        cwd = event.get("cwd")
        if not isinstance(cwd, str) or not Path(cwd).is_absolute():
            raise ValueError("expected an absolute cwd")
        if not isinstance(patch, str):
            raise TypeError("expected an apply_patch command")
        lines = patch.strip().splitlines()
        if not lines or lines[0] != "*** Begin Patch" or lines[-1] != "*** End Patch":
            raise ValueError("expected an apply_patch document")
        paths = []
        for line in lines[1:-1]:
            for header in PATH_HEADERS:
                if line.startswith(header):
                    path = line[len(header):]
                    if not path:
                        raise ValueError("empty patch path")
                    paths.append((Path(cwd) / path).resolve())
                    break
        if not paths:
            raise ValueError("expected a patch file operation")
        for path in paths:
            if path == PROTECTED or PROTECTED in path.parents:
                print("Blocked edit to tests/: test files are protected.", file=sys.stderr)
                return 2
    except (TypeError, ValueError, OSError, RuntimeError) as error:
        print(f"Invalid hook input: {error}", file=sys.stderr)
        return 2
    print("{}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
