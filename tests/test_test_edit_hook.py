"""Exercise the Codex edit guard without attempting to change existing tests."""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / ".codex" / "hooks" / "protect_tests.py"


def _run(command, *, cwd=ROOT):
    event = {
        "hook_event_name": "PreToolUse", "tool_name": "apply_patch",
        "cwd": str(cwd), "tool_input": {"command": command},
    }
    return subprocess.run(
        [sys.executable, str(HOOK)], input=json.dumps(event),
        text=True, capture_output=True, timeout=10, check=False,
    )


def test_guard_blocks_add_update_delete_and_move_paths_in_tests(tmp_path):
    alias = tmp_path / "test_alias"
    alias.symlink_to(ROOT / "tests", target_is_directory=True)
    headers = [
        "*** Add File: tests/new_probe.py\n+pass",
        "*** Update File: tests/test_claims.py\n@@\n-pass\n+pass",
        "*** Delete File: tests/test_status.py",
        "*** Update File: README.md\n*** Move to: tests/moved.md\n@@\n-a\n+b",
        "*** Update File: tests/test_cli.py\n*** Move to: moved.py\n@@\n-a\n+b",
        f"*** Add File: {ROOT / 'tests/nested/probe.py'}\n+pass",
        f"*** Add File: {alias / 'probe.py'}\n+pass",
    ]
    for header in headers:
        result = _run(f"*** Begin Patch\n{header}\n*** End Patch")
        assert result.returncode == 2, result.stdout + result.stderr
        assert "Blocked edit to tests/" in result.stderr
    result = _run(
        "*** Begin Patch\n*** Add File: ../tests/probe.py\n+pass\n*** End Patch",
        cwd=ROOT / "nested",
    )
    assert result.returncode == 2
    assert "Blocked edit to tests/" in result.stderr


def test_guard_allows_other_files_and_ignores_test_paths_in_patch_content():
    result = _run(
        "*** Begin Patch\n*** Update File: claims.py\n@@\n"
        "-old\n+text = 'tests/test_claims.py'\n"
        "+*** Delete File: tests/not_a_header.py\n"
        "*** Add File: tests_extra/example.py\n+pass\n*** End Patch",
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {}


def test_guard_rejects_malformed_events_and_unrecognized_patch_input():
    for payload in ("not JSON", "[]", json.dumps({"tool_input": {}})):
        result = subprocess.run(
            [sys.executable, str(HOOK)], input=payload,
            text=True, capture_output=True, timeout=10, check=False,
        )
        assert result.returncode == 2
        assert "Invalid hook input" in result.stderr
    result = _run("not an apply_patch document")
    assert result.returncode == 2
    assert "Invalid hook input" in result.stderr
