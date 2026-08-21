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
from pathlib import Path

import pytest

README = Path(__file__).resolve().parent.parent / "README.md"
FENCE = re.compile(r"```(\w*)\n(.*?)```", re.DOTALL)


def fences() -> list[tuple[str, str]]:
    return [(m.group(1), m.group(2)) for m in FENCE.finditer(README.read_text("utf-8"))]


def python_blocks() -> list[str]:
    return [body for language, body in fences() if language == "python"]


def _pairs(source: str) -> list[tuple[str, str]]:
    """Every (expression, comment) pair, on one line or on two."""
    out = []
    lines = source.splitlines()
    for number, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "  #" in stripped:  # expr  # literal
            expression, _, comment = stripped.partition("  #")
            out.append((expression.strip(), "#" + comment))
        elif number + 1 < len(lines) and lines[number + 1].strip().startswith("#"):
            out.append((stripped, lines[number + 1].strip()))
    return out


def literal_claims(source: str) -> list[tuple[str, str]]:
    """Pairs of (expression, expected repr) the README asserts are true."""
    claims = []
    for expression, comment in _pairs(source):
        expected = comment.lstrip("#").strip()
        if not expected or expected.startswith("e.g."):
            continue
        try:  # prose comments are not literals, and are left alone
            ast.literal_eval(expected)
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
    assert checked >= 14, f"only {checked} outputs are actually verified"


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
