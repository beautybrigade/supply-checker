"""Shared pytest fixtures.

Every test that touches a CSV works on a temporary copy, never on
sample_supplies.csv itself; a session-wide check enforces that.
"""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SAMPLE = ROOT / "sample_supplies.csv"
sys.path.insert(0, str(ROOT))  # so `import inventory` works from tests/


@pytest.fixture(scope="session", autouse=True)
def sample_file_is_never_modified():
    before = SAMPLE.read_bytes()
    yield
    assert SAMPLE.read_bytes() == before, "a test modified sample_supplies.csv"


@pytest.fixture
def sample_copy(tmp_path):
    """A temporary copy of sample_supplies.csv."""
    path = tmp_path / "supplies.csv"
    shutil.copy(SAMPLE, path)
    return path


@pytest.fixture
def make_csv(tmp_path):
    """Write custom CSV text to a temporary file and return its path."""
    def _make(text, name="custom.csv"):
        path = tmp_path / name
        path.write_text(text, encoding="utf-8")
        return path
    return _make


@pytest.fixture
def run_cli(tmp_path):
    """Run supplies.py as a real command; returns the CompletedProcess."""
    def _run(*args):
        return subprocess.run(
            [sys.executable, str(ROOT / "supplies.py"), *map(str, args)],
            capture_output=True, text=True, cwd=tmp_path,
        )
    return _run
