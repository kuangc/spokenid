"""Every Python block in the README has to run.

A README that has drifted from the code is the fastest way to lose someone in
the first minute, so this runs the blocks in order, in one namespace, the way a
reader following along would.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

README = Path(__file__).resolve().parent.parent / "README.md"
BLOCK = re.compile(r"```python\n(.*?)```", re.DOTALL)


def blocks() -> list[str]:
    return BLOCK.findall(README.read_text(encoding="utf-8"))


def test_the_readme_has_examples() -> None:
    assert len(blocks()) >= 8


def test_every_python_block_runs() -> None:
    namespace: dict[str, object] = {}
    for number, source in enumerate(blocks(), start=1):
        try:
            exec(compile(source, f"README.md block {number}", "exec"), namespace)  # noqa: S102
        except Exception as error:  # pragma: no cover - only on failure
            pytest.fail(f"README block {number} failed: {error!r}\n\n{source}")


def test_the_first_example_appears_early() -> None:
    """A reader should reach working code without scrolling."""
    text = README.read_text(encoding="utf-8")
    first = text.index("```python")
    assert text[:first].count("\n") < 25


def test_the_readme_says_when_not_to_use_it() -> None:
    assert "When not to use this" in README.read_text(encoding="utf-8")
