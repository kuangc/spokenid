"""CI has to actually run the checks, not merely spell them a certain way.

The other policy tests assert how existing steps are written. None of them
noticed when the pytest step, the mypy step, four of the five Python versions,
or the release suite were deleted outright, which is the failure that would
matter. These check that the steps exist and cover what the package claims.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
CI = ROOT / ".github" / "workflows" / "ci.yml"
RELEASE = ROOT / ".github" / "workflows" / "release.yml"


def _workflow(path: Path) -> dict[str, Any]:
    loaded: dict[str, Any] = yaml.safe_load(path.read_text("utf-8"))
    return loaded


def _commands(job: dict[str, Any]) -> list[str]:
    """Every shell command in one job, flattened."""
    out = []
    for step in job.get("steps", []):
        if isinstance(step, dict) and isinstance(step.get("run"), str):
            out.extend(step["run"].splitlines())
    return [line.strip() for line in out if line.strip()]


def _matrix_jobs(workflow: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Jobs that run across several Python versions."""
    return {
        name: job
        for name, job in workflow.get("jobs", {}).items()
        if job.get("strategy", {}).get("matrix", {}).get("python")
    }


@pytest.fixture(scope="module")
def ci() -> dict[str, Any]:
    return _workflow(CI)


@pytest.fixture(scope="module")
def release() -> dict[str, Any]:
    return _workflow(RELEASE)


@pytest.mark.parametrize("tool", ["pytest", "mypy", "ruff check"])
def test_ci_runs_each_check(ci: dict[str, Any], tool: str) -> None:
    everywhere = [line for job in ci["jobs"].values() for line in _commands(job)]
    assert any(tool in line for line in everywhere), (
        f"no CI step runs {tool!r}; deleting it would go unnoticed"
    )


def test_the_test_suite_runs_on_every_python_in_the_matrix(
    ci: dict[str, Any],
) -> None:
    """Not merely somewhere in CI: in the job that spans Python versions.

    A suite that only runs in the packaging job would leave four of the five
    supported versions untested while this file still looked satisfied.
    """
    matrix = _matrix_jobs(ci)
    assert matrix, "no CI job runs across several Python versions"
    assert any(
        any("pytest" in line for line in _commands(job)) for job in matrix.values()
    ), "the Python matrix never runs pytest"


def test_ci_covers_every_python_the_package_claims(ci: dict[str, Any]) -> None:
    """The matrix and the classifiers have to agree."""
    # Read as text: tomllib is 3.11+, and this suite still runs on 3.10.
    claimed = set(
        re.findall(
            r"Programming Language :: Python :: (3\.\d+)",
            (ROOT / "pyproject.toml").read_text("utf-8"),
        )
    )
    tested: set[str] = set()
    for job in ci.get("jobs", {}).values():
        matrix = job.get("strategy", {}).get("matrix", {})
        for value in matrix.get("python", []):
            tested.add(str(value))
        for entry in matrix.get("include", []):
            if "python" in entry:
                tested.add(str(entry["python"]))
    missing = claimed - tested
    assert not missing, f"pyproject claims {sorted(missing)}, CI never runs them"


def test_ci_runs_on_more_than_one_operating_system(ci: dict[str, Any]) -> None:
    systems: set[str] = set()
    for job in ci.get("jobs", {}).values():
        matrix = job.get("strategy", {}).get("matrix", {})
        systems.update(str(v) for v in matrix.get("os", []))
        for entry in matrix.get("include", []):
            if "os" in entry:
                systems.add(str(entry["os"]))
    assert len(systems) >= 2, f"only {systems or 'one'} is tested"


def test_release_runs_the_suite_before_publishing(release: dict[str, Any]) -> None:
    """Publishing something no test has touched is the failure to prevent."""
    jobs = release["jobs"]
    publishing = [
        name
        for name, job in jobs.items()
        if any("pypi-publish" in str(s.get("uses", "")) for s in job.get("steps", []))
    ]
    assert publishing, "no job publishes; this test is watching the wrong file"

    testing = {
        name
        for name, job in jobs.items()
        for step in job.get("steps", [])
        if "pytest" in str(step.get("run", ""))
    }
    assert testing, "the release workflow never runs pytest"

    # every publishing job must depend, directly or through needs, on a test job
    def upstream(name: str, seen: set[str] | None = None) -> set[str]:
        seen = seen or set()
        needs = jobs[name].get("needs", [])
        needs = [needs] if isinstance(needs, str) else list(needs)
        for dependency in needs:
            if dependency not in seen:
                seen.add(dependency)
                upstream(dependency, seen)
        return seen

    for name in publishing:
        assert upstream(name) & testing, (
            f"job {name!r} publishes without depending on a job that runs pytest"
        )
