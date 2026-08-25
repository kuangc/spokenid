"""Policies for a reproducible, least-privilege release path."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RELEASE_WORKFLOW = ROOT / ".github" / "workflows" / "release.yml"
RELEASING = ROOT / "RELEASING.md"

BENCHMARK_CHECK = (
    "uv run --locked python benchmarks/evaluate.py --profile full "
    "--check benchmarks/results/v0.1.json"
)


def test_release_build_uses_the_locked_project_toolchain() -> None:
    workflow = RELEASE_WORKFLOW.read_text("utf-8")
    build = workflow.split("  build:", 1)[1].split("  publish:", 1)[0]

    assert "uv sync --locked" in build
    assert BENCHMARK_CHECK in build
    assert "uv build --no-build-isolation" in build
    assert "uv run --locked twine check --strict dist/*" in build
    assert "uvx twine" not in build


def test_build_is_unprivileged_and_oidc_is_confined_to_publish() -> None:
    workflow = RELEASE_WORKFLOW.read_text("utf-8")
    build = workflow.split("  build:", 1)[1].split("  publish:", 1)[0]
    publish = workflow.split("  publish:", 1)[1]

    assert "id-token" not in build
    assert "id-token: write" in publish
    assert "contents: read" not in publish
    assert "pypa/gh-action-pypi-publish@" in publish


def test_local_release_checklist_uses_the_locked_toolchain_and_artifact() -> None:
    instructions = RELEASING.read_text("utf-8")

    assert "uv sync --locked" in instructions
    assert BENCHMARK_CHECK in instructions
    assert "uv build --no-build-isolation" in instructions
    assert "uv run --locked twine check --strict dist/*" in instructions
    assert "uvx twine" not in instructions


def test_ci_and_local_release_checks_run_the_unpacked_sdist_suite() -> None:
    workflow = RELEASE_WORKFLOW.read_text("utf-8")
    instructions = RELEASING.read_text("utf-8")

    for text in (workflow, instructions):
        assert "tar -xzf dist/spokenid-*.tar.gz" in text
        assert "uv run --locked pytest -q" in text


def test_every_release_project_command_asserts_the_lock_is_current() -> None:
    workflow = RELEASE_WORKFLOW.read_text("utf-8")

    assert "--frozen" not in workflow
    for line in workflow.splitlines():
        if "uv run " in line:
            assert "uv run --locked " in line


def test_release_requires_a_dated_changelog_heading() -> None:
    workflow = RELEASE_WORKFLOW.read_text("utf-8")

    assert r"^## \[$version\] - [0-9]{4}-[0-9]{2}-[0-9]{2}$" in workflow


def test_first_release_changelog_instructions_use_the_existing_section() -> None:
    instructions = RELEASING.read_text("utf-8")

    assert (
        "For `v0.1.0`, add the release date to the existing `## [0.1.0]` section; "
        "do not create a second section."
    ) in " ".join(instructions.split())


def test_first_release_install_instructions_quote_the_current_readme() -> None:
    instructions = RELEASING.read_text("utf-8")

    assert "Not on PyPI yet. Install the current repository with:" in instructions
    assert "Not on PyPI yet. Until it is:" not in instructions
    assert "pip install git+https://github.com/kuangc/spokenid" in instructions
    assert "pip install spokenid" in instructions


def test_release_instructions_have_balanced_code_fences() -> None:
    instructions = RELEASING.read_text("utf-8")

    assert instructions.count("```") % 2 == 0


def test_sdist_includes_the_top_level_support_files_its_tests_read() -> None:
    project = (ROOT / "pyproject.toml").read_text("utf-8")

    for filename in (
        "CHANGELOG.md",
        "CONTRIBUTING.md",
        "README.md",
        "RELEASING.md",
        "SECURITY.md",
    ):
        assert f'"{filename}"' in project
