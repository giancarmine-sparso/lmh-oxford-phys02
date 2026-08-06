from pathlib import Path
import subprocess
import sys

import pytest


PROJECT_DIR = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    "script",
    ("inspect_sample.py", "plot_mt.py", "run_abcd.py"),
)
def test_cli_help(script: str) -> None:
    completed = subprocess.run(
        [sys.executable, str(PROJECT_DIR / "scripts" / script), "--help"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    assert "usage:" in completed.stdout
