"""The README has to be true, not merely runnable.

Every ``python`` block is executed in order in one namespace, the way a reader
following along would. On top of that:

* A line of the form ``expression`` followed by ``# <literal>`` is evaluated and
  compared against that literal. Write ``# e.g. '7HW2-0J46'`` instead when the
  value is random, and it is treated as illustration rather than a claim.
* A ``python`` block that prints, followed by a plain fenced block, has its
  output compared against that block character for character.

An earlier version of this file only checked that the blocks ran, which let a
wrong figure sit in the sizing table through a full CI run.
"""

from __future__ import annotations

import ast
import contextlib
import io
import re
import shutil
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

import pytest

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover - exercised by the Python 3.10 CI job
    import tomli as tomllib  # type: ignore[import-not-found]

README = Path(__file__).resolve().parent.parent / "README.md"
SECURITY = README.parent / "SECURITY.md"
FENCE = re.compile(r"```(\w*)\n(.*?)```", re.DOTALL)
EMAIL = re.compile(
    rb"[A-Z0-9.!#$%&'*+/=?^_`{|}~-]+@"
    rb"[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?"
    rb"(?:\.[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?)+",
    re.IGNORECASE,
)

APPROVED_ALPHABET_WORDING = (
    "Excludes A/E/I/O/U and the common letter-digit confusables, reducing "
    "accidental words and ambiguous transcription."
)


def fences() -> list[tuple[str, str]]:
    return [(m.group(1), m.group(2)) for m in FENCE.finditer(README.read_text("utf-8"))]


def python_blocks() -> list[str]:
    return [body for language, body in fences() if language == "python"]


def _pairs(source: str) -> list[tuple[str, str]]:
    """Every (expression, comment) pair, on one line and on the next.

    Both, not either. An earlier version stopped at a trailing comment, so
    `scheme.parse(x).exact  # already right` followed by `# True` had the prose
    taken as the claim and the actual value never checked.
    """
    out = []
    lines = source.splitlines()
    for number, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        expression = stripped
        # Split at the first `#` whose left side is a complete expression, so
        # one space is as good as two and a `#` inside a string is left alone.
        for index, character in enumerate(stripped):
            if character != "#" or index == 0 or not stripped[index - 1].isspace():
                continue
            candidate = stripped[:index].strip()
            try:
                ast.parse(candidate, mode="eval")
            except (ValueError, SyntaxError):
                continue
            expression = candidate
            out.append((expression, stripped[index:]))
            break
        if number + 1 < len(lines) and lines[number + 1].strip().startswith("#"):
            out.append((expression, lines[number + 1].strip()))
    return out


def literal_claims(source: str) -> list[tuple[str, str]]:
    """Pairs of (expression, expected repr) the README asserts are true."""
    claims = []
    for expression, comment in _pairs(source):
        expected = comment.lstrip("#").strip()
        if not expected or expected.startswith("e.g."):
            continue
        # ast.parse rather than literal_eval, so a repr of one of the
        # library's own dataclasses counts as a claim. Prose does not parse.
        try:
            ast.parse(expected, mode="eval")
        except (ValueError, SyntaxError):
            continue
        try:
            ast.parse(expression, mode="eval")
        except SyntaxError:
            continue
        claims.append((expression, expected))
    return claims


def test_the_readme_has_examples() -> None:
    assert len(python_blocks()) >= 8


def test_the_first_example_appears_early() -> None:
    text = README.read_text("utf-8")
    assert text[: text.index("```python")].count("\n") < 25


def test_the_readme_says_when_not_to_use_it() -> None:
    assert "When not to use this" in README.read_text("utf-8")


def test_the_stated_default_sample_is_a_valid_default_identifier() -> None:
    from spokenid import Scheme

    match = re.search(r"The default looks like `([^`]+)`", README.read_text("utf-8"))
    assert match, "the opening default sample is missing"
    assert Scheme().validate(match.group(1)), match.group(1)


def test_the_package_doctest_does_not_consume_a_repaired_value() -> None:
    import spokenid

    documentation = spokenid.__doc__ or ""
    assert 'parse("o000-oooo").value' not in documentation
    assert 'parse("0000-0000").value' in documentation


def test_editorial_source_notes_match_the_current_checker_design() -> None:
    root = README.parent
    alphabet_source = (root / "src/spokenid/alphabet.py").read_text("utf-8")
    contributing = (root / "CONTRIBUTING.md").read_text("utf-8")

    assert "no letter that looks like a digit" not in alphabet_source
    assert (
        "Any 26-character alphabet with `check=True` uses `Damm`; other supported "
        "even sizes use `Luhn`; an odd-sized `Luhn` fallback is refused."
        in " ".join(contributing.split())
    )
    for path in (
        "tests/test_damm.py",
        "tests/test_check.py",
        "tests/test_properties.py",
        "tests/test_evaluation.py",
    ):
        assert path in contributing
    assert "only catches every single-character mistake" not in contributing
    assert "uv run --locked ruff format --check ." in contributing
    assert (
        "CI runs pytest on Python 3.10 through 3.14; mypy and Ruff run once."
        in " ".join(contributing.split())
    )
    assert "CI runs all of these" not in contributing


def test_the_readme_makes_only_the_approved_public_claims() -> None:
    text = README.read_text("utf-8")
    prose = " ".join(text.split())

    assert APPROVED_ALPHABET_WORDING in text
    assert "every one-symbol in-alphabet substitution" in text
    assert "every adjacent unequal-symbol transposition" in text
    assert "including the check character" in text
    assert "arbitrary multiple errors" in text
    assert "non-adjacent swaps" in text
    assert "fixed-length parsing" in text.lower()

    assert "explicit confirmation" in text
    assert "same database transaction" in text
    assert "unique index" in text

    assert "https://github.com/kuangc/spokenid/blob/main/benchmarks/README.md" in text
    assert (
        "https://github.com/kuangc/spokenid/blob/main/benchmarks/results/v0.1.json"
        in text
    )
    assert "synthetic cohorts" in text
    assert "not human-error frequencies" in text

    assert "seven information symbols" in prose
    assert "Only `random()` draws those symbols randomly" in prose
    assert "Counted references remain enumerable" in prose
    assert "Do not rely on larger or varying steps" in prose
    assert "uniformly from the full identifier space" in prose
    assert "without knowing how identifiers were allocated" in prose
    assert "about 1 in 54,295,037" in prose
    assert "seven random ones" not in text


def test_install_instructions_are_coherent_for_the_release_state() -> None:
    text = README.read_text("utf-8")
    pre_release = "Not on PyPI yet" in text
    repository_install = "pip install git+https://github.com/kuangc/spokenid" in text
    pypi_install = re.search(r"(?m)^pip install spokenid$", text) is not None

    assert (pre_release, repository_install, pypi_install) in {
        (True, True, False),
        (False, False, True),
    }


def test_security_guidance_distinguishes_random_drawing_from_guess_resistance() -> None:
    text = SECURITY.read_text("utf-8")
    prose = " ".join(text.split())

    assert "cryptographically strong generator" in prose
    assert "does not encode issue order" in prose
    assert "guess resistance still depends on length and population" in prose
    assert "Do not rely on gaps to hide the sequence" in prose
    assert "is unpredictable" not in prose


def test_the_readme_omits_unsupported_or_review_process_claims() -> None:
    text = README.read_text("utf-8").lower()

    forbidden = (
        "any language",
        "realistic mix",
        "simulated day",
        "forty thousand lookups",
        "`next(step=1)` | 64%",
        "`next(step=random.randint(1, 50))` | 95%",
        "review round",
        "reviewer",
    )
    assert not [claim for claim in forbidden if claim in text]


def test_the_changelog_is_a_release_summary_not_a_review_diary() -> None:
    changelog = (README.parent / "CHANGELOG.md").read_text("utf-8")
    assert "## [Unreleased]" in changelog
    release = re.search(r"(?ms)^## \[0\.1\.0\][^\n]*\n(.*?)(?=^## \[|\Z)", changelog)
    assert release, "the 0.1.0 changelog section is missing"
    release_text = release.group(1)
    bullets = [line for line in release_text.splitlines() if line.startswith("- ")]
    assert 5 <= len(bullets) <= 8
    assert "reviewer" not in release_text.lower()
    assert "timing" not in release_text.lower()


def test_package_metadata_omits_personal_contact_and_untested_runtime() -> None:
    metadata_text = (README.parent / "pyproject.toml").read_text("utf-8")
    metadata = tomllib.loads(metadata_text)["project"]

    assert metadata["description"] == (
        "Short identifiers designed to be read aloud, written down, and typed back."
    )
    authors = metadata["authors"]
    assert authors
    assert all(isinstance(author, dict) and "email" not in author for author in authors)
    assert not [
        classifier
        for classifier in metadata["classifiers"]
        if classifier == "Programming Language :: Python :: Implementation :: PyPy"
    ]


def _public_source_files() -> list[Path]:
    git = shutil.which("git")
    if git is not None and (README.parent / ".git").exists():
        listed = subprocess.run(  # noqa: S603
            [git, "ls-files", "-z"],
            cwd=README.parent,
            capture_output=True,
            check=True,
        ).stdout
        return sorted(
            path
            for raw in listed.split(b"\0")
            if raw
            if (path := README.parent / raw.decode("utf-8")).is_file()
        )

    # An unpacked sdist has no Git metadata; every remaining file is public.
    ignored = {
        ".git",
        ".hypothesis",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".venv",
        ".worktrees",
        "__pycache__",
        "build",
        "dist",
    }
    return sorted(
        path
        for path in README.parent.rglob("*")
        if path.is_file()
        and not path.is_symlink()
        and not ignored.intersection(path.relative_to(README.parent).parts)
        and path.name != ".coverage"
    )


def _assert_no_email(payload: bytes, source: str) -> None:
    match = EMAIL.search(payload)
    assert match is None, f"public release data contains an email address: {source}"


def test_public_source_and_built_artifacts_contain_no_email_addresses(
    tmp_path: Path,
) -> None:
    for path in _public_source_files():
        _assert_no_email(path.read_bytes(), path.relative_to(README.parent).as_posix())

    uv = shutil.which("uv")
    assert uv is not None, "the test suite requires uv"
    output = tmp_path / "dist"
    finished = subprocess.run(  # noqa: S603
        [
            uv,
            "build",
            "--python",
            sys.executable,
            "--no-build-isolation",
            "--out-dir",
            str(output),
        ],
        cwd=README.parent,
        capture_output=True,
        text=True,
        check=False,
    )
    assert finished.returncode == 0, finished.stdout + finished.stderr

    artifacts = sorted(
        path for path in output.iterdir() if path.suffix in {".gz", ".whl"}
    )
    assert len(artifacts) == 2
    assert {path.suffix for path in artifacts} == {".gz", ".whl"}
    for artifact in artifacts:
        if artifact.suffix == ".whl":
            with zipfile.ZipFile(artifact) as archive:
                for zip_member in archive.infolist():
                    if not zip_member.is_dir():
                        _assert_no_email(
                            archive.read(zip_member),
                            f"{artifact.name}:{zip_member.filename}",
                        )
        else:
            with tarfile.open(artifact, "r:gz") as archive:
                for tar_member in archive.getmembers():
                    if tar_member.isfile():
                        extracted = archive.extractfile(tar_member)
                        assert extracted is not None
                        _assert_no_email(
                            extracted.read(), f"{artifact.name}:{tar_member.name}"
                        )


def test_cli_requires_exact_resubmission_after_a_lookalike_repair() -> None:
    repaired = subprocess.run(
        [sys.executable, "-m", "spokenid", "check", "7hw2-oj43"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert repaired.returncode == 2
    assert repaired.stdout == ""
    assert "7HW2-0J43" in repaired.stderr
    assert "character 6" in repaired.stderr

    exact = subprocess.run(
        [sys.executable, "-m", "spokenid", "check", "7HW2-0J43"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert exact.returncode == 0
    assert exact.stdout == "7HW2-0J43\n"
    assert exact.stderr == ""


def test_every_python_block_runs_and_every_claim_holds() -> None:
    namespace: dict[str, object] = {}
    checked = 0
    for number, source in enumerate(python_blocks(), start=1):
        try:
            exec(compile(source, f"README.md block {number}", "exec"), namespace)  # noqa: S102
        except Exception as error:  # pragma: no cover - only on failure
            pytest.fail(f"README block {number} failed: {error!r}\n\n{source}")
        for expression, expected in literal_claims(source):
            actual = repr(eval(expression, namespace))  # noqa: S307
            assert actual == expected, (
                f"README block {number} claims `{expression}` is {expected}, "
                f"but it is {actual}"
            )
            checked += 1
    # Derived, not hardcoded: every value-shaped comment on the page has to be
    # one of the claims that just got checked, so none can be quietly dropped.
    shown = sum(len(literal_claims(block)) for block in python_blocks())
    assert checked == shown, f"{shown - checked} shown values were skipped"
    assert checked >= 15, f"only {checked} outputs are verified; the page has been gutted"


def test_lookup_example_never_queries_a_repaired_identifier() -> None:
    namespace: dict[str, object] = {}
    for source in python_blocks():
        exec(compile(source, "README.md", "exec"), namespace)  # noqa: S102

    find = namespace["find"]
    assert callable(find)

    class ObservedRecords(dict[str, object]):
        queried = False

        def __contains__(self, key: object) -> bool:
            self.queried = True
            return super().__contains__(key)

        def __getitem__(self, key: str) -> object:
            self.queried = True
            return super().__getitem__(key)

    canonical = "7HW2-0J43"
    member = object()
    records = ObservedRecords({canonical: member})

    matches, confirmation, suggestions = find("7hw2 oj43", records)
    assert not records.queried
    assert matches == []
    assert confirmation["prompt"] == f"Confirm {canonical}, then submit it again"
    assert confirmation["repairs"]
    assert suggestions == ()

    for invalid in ("0000-001W", "OOOO-OOO1", "nope"):
        matches, confirmation, suggestions = find(invalid, records)
        assert not records.queried
        assert matches == []
        assert confirmation is None
        assert suggestions == ()

    matches, confirmation, suggestions = find(
        "0000-001W", records, offer_suggestions=True
    )
    assert not records.queried
    assert matches == []
    assert confirmation is None
    assert "0000-0012" in suggestions

    matches, confirmation, suggestions = find(canonical, records)
    assert records.queried
    assert matches == [member]
    assert confirmation is None
    assert suggestions == ()

    records.queried = False
    matches, confirmation, suggestions = find(" 7hw2 0j43 ", records)
    assert records.queried
    assert matches == [member]
    assert confirmation is None
    assert suggestions == ()


def test_printed_output_matches_the_block_that_follows() -> None:
    """A `python` block that prints, then a plain block showing what it printed."""
    namespace: dict[str, object] = {}
    for source in python_blocks():
        exec(compile(source, "README.md", "exec"), namespace)  # noqa: S102

    everything = fences()
    compared = 0
    for index, (language, source) in enumerate(everything[:-1]):
        following_language, following = everything[index + 1]
        if language != "python" or following_language != "" or "print(" not in source:
            continue
        captured = io.StringIO()
        with contextlib.redirect_stdout(captured):
            exec(compile(source, "README.md", "exec"), dict(namespace))  # noqa: S102
        assert captured.getvalue().strip() == following.strip(), (
            f"the block after `{source.strip()}` does not match what it prints"
        )
        compared += 1
    assert compared >= 1, "no printed output is being compared"


def test_every_public_name_is_documented() -> None:
    """If it is exported, a reader has to be able to find out what it is."""
    import spokenid

    words = set(README.read_text("utf-8").replace("`", " ").split())
    missing = sorted(
        name
        for name in spokenid.__all__
        if not name.startswith("__") and name not in words
    )
    assert not missing, f"exported but never mentioned in the README: {missing}"


def test_console_examples_really_print_that() -> None:
    """Every `$ spokenid ...` block is run, and its shown output must appear.

    A line of `...` stands for output left out. Everything else has to match.
    """
    import subprocess
    import sys

    ran = 0
    for language, body in fences():
        if language != "console":
            continue
        lines = body.strip().splitlines()
        assert lines[0].startswith("$ "), body
        command = lines[0][2:].split()
        assert command[0] == "spokenid", command
        finished = subprocess.run(  # noqa: S603
            [sys.executable, "-m", "spokenid", *command[1:]],
            capture_output=True,
            text=True,
            check=False,
        )
        printed = finished.stdout + finished.stderr
        for shown in lines[1:]:
            if shown.strip() in {"", "..."}:
                continue
            assert shown in printed, (
                f"`{lines[0]}` never prints {shown!r}\nit prints:\n{printed}"
            )
        ran += 1
    assert ran >= 1, "no console examples are being run"
