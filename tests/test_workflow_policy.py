"""The workflow supply-chain policy is enforced without network access."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SHELL_SCRIPT = ROOT / "scripts" / "check_action_refs.sh"
CHECKER = ROOT / "scripts" / "check_action_refs.py"
PYPROJECT = ROOT / "pyproject.toml"
CI_WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
RELEASE_WORKFLOW = ROOT / ".github" / "workflows" / "release.yml"
SHA = "0123456789abcdef0123456789abcdef01234567"


def run_policy(
    tmp_path: Path,
    workflow: str,
    *,
    workflow_name: str = "ci.yml",
    action: str | None = None,
    action_name: str = "action.yml",
    action_symlink: Path | None = None,
    local_workflow: str | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run the policy against one isolated workflow."""
    workflow_dir = tmp_path / ".github" / "workflows"
    workflow_dir.mkdir(parents=True)
    (workflow_dir / workflow_name).write_text(workflow, encoding="utf-8")
    if local_workflow is not None:
        (workflow_dir / "shared.yml").write_text(local_workflow, encoding="utf-8")
    if action is not None:
        action_dir = tmp_path / ".github" / "actions" / "check"
        action_dir.mkdir(parents=True)
        (action_dir / action_name).write_text(action, encoding="utf-8")
    if action_symlink is not None:
        action_root = tmp_path / ".github" / "actions"
        action_root.mkdir(parents=True)
        (action_root / "check").symlink_to(action_symlink, target_is_directory=True)

    return subprocess.run(  # noqa: S603
        [sys.executable, str(CHECKER)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )


def test_rejects_a_mutable_action_tag(tmp_path: Path) -> None:
    result = run_policy(tmp_path, "steps:\n  - uses: actions/checkout@v7 # v7.0.0\n")

    assert result.returncode != 0
    assert "40-character commit SHA" in result.stderr


@pytest.mark.parametrize("key", ["uses :", '"uses":', "'uses' :"])
def test_rejects_mutable_refs_with_valid_yaml_key_spellings(
    tmp_path: Path, key: str
) -> None:
    result = run_policy(tmp_path, f"steps:\n  - {key} actions/checkout@v7 # v7.0.0\n")

    assert result.returncode != 0
    assert "40-character commit SHA" in result.stderr


def test_rejects_a_pin_without_a_version_comment(tmp_path: Path) -> None:
    result = run_policy(tmp_path, f"steps:\n  - uses: actions/checkout@{SHA}\n")

    assert result.returncode != 0
    assert "version comment" in result.stderr


def test_rejects_a_mutable_reusable_workflow(tmp_path: Path) -> None:
    result = run_policy(
        tmp_path,
        "jobs:\n  shared:\n    uses: example/project/.github/workflows/ci.yml@v1 # v1\n",
    )

    assert result.returncode != 0
    assert "40-character commit SHA" in result.stderr


def test_checks_yaml_workflow_files_too(tmp_path: Path) -> None:
    result = run_policy(
        tmp_path,
        "steps:\n  - uses: actions/checkout@v7 # v7\n",
        workflow_name="ci.yaml",
    )

    assert result.returncode != 0
    assert "40-character commit SHA" in result.stderr


def test_checks_dependencies_inside_local_actions(tmp_path: Path) -> None:
    result = run_policy(
        tmp_path,
        "steps:\n  - uses: ./.github/actions/check\n",
        action=(
            "runs:\n  using: composite\n  steps:\n    - uses: actions/checkout@v7 # v7\n"
        ),
    )

    assert result.returncode != 0
    assert ".github/actions/check/action.yml" in result.stderr


def test_checks_dependencies_inside_local_reusable_workflows(tmp_path: Path) -> None:
    result = run_policy(
        tmp_path,
        "jobs:\n  shared:\n    uses: ./.github/workflows/shared.yml\n",
        local_workflow="steps:\n  - uses: actions/checkout@v7 # v7\n",
    )

    assert result.returncode != 0
    assert ".github/workflows/shared.yml" in result.stderr
    assert "40-character commit SHA" in result.stderr


def test_checks_action_yaml_manifests_too(tmp_path: Path) -> None:
    result = run_policy(
        tmp_path,
        "steps:\n  - uses: ./.github/actions/check\n",
        action=(
            "runs:\n  using: composite\n  steps:\n    - uses: actions/checkout@v7 # v7\n"
        ),
        action_name="action.yaml",
    )

    assert result.returncode != 0
    assert ".github/actions/check/action.yaml" in result.stderr


def test_checks_quoted_uses_keys_inside_local_actions(tmp_path: Path) -> None:
    result = run_policy(
        tmp_path,
        "steps:\n  - uses: ./.github/actions/check\n",
        action=(
            "runs:\n  using: composite\n  steps:\n"
            '    - "uses" : actions/checkout@v7 # v7\n'
        ),
    )

    assert result.returncode != 0
    assert ".github/actions/check/action.yml" in result.stderr
    assert "40-character commit SHA" in result.stderr


def test_rejects_a_missing_local_action(tmp_path: Path) -> None:
    result = run_policy(tmp_path, "steps:\n  - uses: ./.github/actions/check\n")

    assert result.returncode != 0
    assert "has no action.yml or action.yaml" in result.stderr


def test_local_action_symlinks_cannot_escape_the_repository(tmp_path: Path) -> None:
    outside = tmp_path.parent / f"{tmp_path.name}-outside"
    outside.mkdir()
    (outside / "action.yml").write_text(
        "runs:\n  using: composite\n  steps: []\n", encoding="utf-8"
    )
    try:
        result = run_policy(
            tmp_path,
            "steps:\n  - uses: ./.github/actions/check\n",
            action_symlink=outside,
        )
    except OSError as error:
        pytest.skip(f"symlinks unavailable: {error}")

    assert result.returncode != 0
    assert "resolves outside the repository" in result.stderr


def test_rejects_a_multiline_uses_value(tmp_path: Path) -> None:
    result = run_policy(tmp_path, "steps:\n  - uses: >\n      actions/checkout@v7\n")

    assert result.returncode != 0
    assert "40-character commit SHA" in result.stderr


def test_finds_uses_inside_a_flow_mapping(tmp_path: Path) -> None:
    result = run_policy(
        tmp_path, "steps: [{uses: actions/checkout@v7, name: checkout}]\n"
    )

    assert result.returncode != 0
    assert "40-character commit SHA" in result.stderr


def test_finds_uses_inside_a_flow_sequence(tmp_path: Path) -> None:
    result = run_policy(
        tmp_path, "steps: [uses: actions/checkout@v7] # deliberately mutable\n"
    )

    assert result.returncode != 0
    assert "40-character commit SHA" in result.stderr


def test_decodes_escaped_uses_keys(tmp_path: Path) -> None:
    result = run_policy(tmp_path, 'steps:\n  - "u\\u0073es": actions/checkout@v7 # v7\n')

    assert result.returncode != 0
    assert "40-character commit SHA" in result.stderr


def test_resolves_aliases_before_checking_the_reference(tmp_path: Path) -> None:
    result = run_policy(
        tmp_path,
        "checkout: &checkout actions/checkout@v7 # v7\nsteps:\n  - uses: *checkout\n",
    )

    assert result.returncode != 0
    assert "actions/checkout@v7" in result.stderr


def test_alias_comment_must_be_on_the_uses_line(tmp_path: Path) -> None:
    result = run_policy(
        tmp_path,
        f"checkout: &checkout actions/checkout@{SHA} # v7\nsteps:\n  - uses: *checkout\n",
    )

    assert result.returncode != 0
    assert "same-line version comment" in result.stderr


def test_alias_uses_its_own_line_for_the_version_comment(tmp_path: Path) -> None:
    result = run_policy(
        tmp_path,
        f"checkout: &checkout actions/checkout@{SHA}\nsteps:\n  - uses: *checkout # v7\n",
    )

    assert result.returncode == 0, result.stderr


def test_malformed_yaml_fails_closed(tmp_path: Path) -> None:
    result = run_policy(tmp_path, "steps: [uses: actions/checkout@v7\n")

    assert result.returncode != 0
    assert "YAML parse error" in result.stderr


def test_custom_yaml_tags_fail_closed(tmp_path: Path) -> None:
    result = run_policy(
        tmp_path, f"steps:\n  - uses: !unsafe actions/checkout@{SHA} # v7\n"
    )

    assert result.returncode != 0
    assert "unsupported YAML tag" in result.stderr


def test_non_string_uses_values_fail_closed(tmp_path: Path) -> None:
    result = run_policy(tmp_path, "steps:\n  - uses: [actions/checkout@v7]\n")

    assert result.returncode != 0
    assert "uses value must be a string" in result.stderr


def test_rejects_docker_references_explicitly(tmp_path: Path) -> None:
    result = run_policy(
        tmp_path, f"steps:\n  - uses: docker://ghcr.io/acme/tool@{SHA} # v1\n"
    )

    assert result.returncode != 0
    assert "Docker action references are not supported" in result.stderr


def test_rejects_other_uri_schemes(tmp_path: Path) -> None:
    result = run_policy(
        tmp_path, f"steps:\n  - uses: https://example.com/action@{SHA} # v1\n"
    )

    assert result.returncode != 0
    assert "40-character commit SHA" in result.stderr


def test_accepts_an_immutable_pin_with_a_version_comment(tmp_path: Path) -> None:
    result = run_policy(tmp_path, f"steps:\n  - uses: actions/checkout@{SHA} # v7.0.0\n")

    assert result.returncode == 0, result.stderr


def test_accepts_a_pinned_reusable_workflow(tmp_path: Path) -> None:
    workflow = (
        "jobs:\n  shared:\n"
        f"    uses: example/project/.github/workflows/ci.yml@{SHA} # v1\n"
    )
    result = run_policy(
        tmp_path,
        workflow,
    )

    assert result.returncode == 0, result.stderr


def test_accepts_a_pinned_flow_mapping_with_an_escaped_key(tmp_path: Path) -> None:
    result = run_policy(
        tmp_path, f'steps: [{{"u\\u0073es": actions/checkout@{SHA}}}] # v7\n'
    )

    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("quote", ['"', "'"])
def test_quoted_sibling_text_is_not_a_version_comment(tmp_path: Path, quote: str) -> None:
    workflow = (
        f"steps: [{{uses: actions/checkout@{SHA}, "
        f"name: {quote}# v7 not-a-comment{quote}}}]\n"
    )
    result = run_policy(tmp_path, workflow)

    assert result.returncode != 0
    assert "same-line version comment" in result.stderr


def test_real_comment_after_quoted_sibling_is_accepted(tmp_path: Path) -> None:
    workflow = f'steps: [{{uses: actions/checkout@{SHA}, name: "# v6 fake"}}] # v7\n'
    result = run_policy(tmp_path, workflow)

    assert result.returncode == 0, result.stderr


def test_local_actions_do_not_need_a_remote_version(tmp_path: Path) -> None:
    result = run_policy(
        tmp_path,
        "steps:\n  - uses: ./.github/actions/check\n",
        action="runs:\n  using: composite\n  steps: []\n",
    )

    assert result.returncode == 0, result.stderr


def test_sdist_contains_the_policy_used_by_its_tests() -> None:
    pyproject = PYPROJECT.read_text(encoding="utf-8")
    sdist = pyproject.split("[tool.hatch.build.targets.sdist]", 1)[1].split("[tool.", 1)[
        0
    ]

    assert '"scripts"' in sdist
    assert '".github/workflows"' in sdist
    assert '"CONTRIBUTING.md"' in sdist
    assert '"uv.lock"' in sdist


def test_shell_wrapper_and_ci_use_the_locked_checker_environment() -> None:
    wrapper = SHELL_SCRIPT.read_text(encoding="utf-8")
    ci = CI_WORKFLOW.read_text(encoding="utf-8")

    assert 'uv run --project "$project_root" --locked' in wrapper
    assert 'cd -- "$project_root"' in wrapper
    setup = ci.index("astral-sh/setup-uv@", ci.index("quality:"))
    sync = ci.index("uv sync --locked", setup)
    policy = ci.index("bash scripts/check_action_refs.sh", sync)
    assert setup < sync < policy


def test_release_verifies_the_tagged_commit_is_on_main() -> None:
    release = RELEASE_WORKFLOW.read_text(encoding="utf-8")

    assert "fetch-depth: 0" in release
    assert "refs/heads/main:refs/remotes/origin/main" in release
    assert "git show-ref --verify --quiet refs/remotes/origin/main" in release
    assert 'git rev-parse "${GITHUB_SHA}^{commit}"' in release
    assert 'git merge-base --is-ancestor "$tagged_commit" origin/main' in release
