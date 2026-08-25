"""Release-evidence and build-toolchain policy for continuous integration."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = ROOT / "pyproject.toml"
LOCK = ROOT / "uv.lock"
CI = ROOT / ".github" / "workflows" / "ci.yml"

BENCHMARK_CHECK = (
    "uv run --locked python benchmarks/evaluate.py --profile full "
    "--check benchmarks/results/v0.1.json"
)


def test_build_backend_is_pinned_exactly() -> None:
    project = PYPROJECT.read_text("utf-8")

    assert 'requires = ["hatchling==1.32.0"]' in project


def test_release_tools_are_exact_project_dependencies() -> None:
    project = PYPROJECT.read_text("utf-8")
    dev = project.split("[dependency-groups]", 1)[1].split("[tool.uv]", 1)[0]

    assert '"hatchling==1.32.0"' in dev
    assert '"twine==7.0.0"' in dev


def test_lock_contains_the_exact_release_tools() -> None:
    locked = LOCK.read_text("utf-8")

    assert re.search(r'(?ms)^name = "hatchling"\nversion = "1\.32\.0"$', locked)
    assert re.search(r'(?ms)^name = "twine"\nversion = "7\.0\.0"$', locked)


def test_ci_checks_the_committed_full_evaluation() -> None:
    workflow = CI.read_text("utf-8")

    assert BENCHMARK_CHECK in workflow


def test_ci_build_uses_the_locked_project_toolchain() -> None:
    workflow = CI.read_text("utf-8")
    package = workflow.split("  package:", 1)[1]

    assert "uv sync --locked" in package
    assert "uv build --no-build-isolation" in package
    assert "uv run --locked twine check --strict dist/*" in package
    assert "uvx twine" not in package


def test_ci_runs_the_shipped_suite_from_the_unpacked_sdist() -> None:
    package = CI.read_text("utf-8").split("  package:", 1)[1]

    assert "Test the unpacked source distribution" in package
    assert "tar -xzf dist/spokenid-*.tar.gz" in package
    assert "uv run --locked pytest -q" in package


def test_every_ci_project_command_asserts_the_lock_is_current() -> None:
    workflow = CI.read_text("utf-8")

    assert "--frozen" not in workflow
    for line in workflow.splitlines():
        if "uv run " in line:
            assert "uv run --locked " in line
