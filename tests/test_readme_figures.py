"""Numbers written in the README prose, checked against the code.

The README's persuasive power rests on its figures being exactly right, and a
figure in a sentence is not caught by running the code blocks. Each one here is
derived from the library and then required to appear in the text, so neither can
drift without a failure.
"""

from __future__ import annotations

import builtins
import itertools
import re
from pathlib import Path

import pytest

from spokenid import SPOKEN, Alphabet, Luhn, Scheme

README = Path(__file__).resolve().parent.parent / "README.md"


@pytest.fixture(scope="module")
def text() -> str:
    return README.read_text("utf-8")


def test_the_alphabet_size_in_prose(text: str) -> None:
    assert len(SPOKEN) == 26
    assert "Twenty-six characters" in text


def test_the_odd_alphabet_size_in_prose(text: str) -> None:
    odd = Alphabet.derive(lookalikes={"I": "1", "O": "0", "B": "8", "S": "5"})
    assert len(odd) == 29
    assert "# 29" in text


def test_the_number_of_collisions_before_giving_up(text: str) -> None:
    scheme = Scheme(length=4)
    attempts = 0

    def taken(_: str) -> bool:
        nonlocal attempts
        attempts += 1
        return True

    with pytest.raises(Exception, match="outgrown"):
        scheme.random(taken=taken)
    assert attempts == 10
    assert "After ten collisions in a row" in text


def _swap_detection(alphabet: str) -> float:
    luhn = Luhn(Alphabet(alphabet))
    caught = total = 0
    for body in itertools.product(alphabet, repeat=3):
        joined = "".join(body)
        full = joined + luhn.compute(joined)
        for position in range(2):
            if full[position] == full[position + 1]:
                continue
            total += 1
            swapped = (
                full[:position]
                + full[position + 1]
                + full[position]
                + full[position + 2 :]
            )
            caught += not luhn.verify(swapped)
    return caught / total


def test_the_swap_detection_rate_in_prose(text: str) -> None:
    rate = _swap_detection(SPOKEN.characters)
    assert 0.995 < rate < 0.998, rate
    assert "about 99.7% of swaps" in text


def test_the_odd_alphabet_miss_rate_in_prose(text: str) -> None:
    """The README says roughly one mistake in forty slips through."""
    odd = Alphabet.derive(lookalikes={"I": "1", "O": "0", "B": "8", "S": "5"})

    def check(body: str) -> str:
        chars, size, factor, total = odd.characters, len(odd), 2, 0
        for char in reversed(body):
            addend = factor * chars.index(char)
            factor = 1 if factor == 2 else 2
            total += addend // size + addend % size
        return chars[(size - total % size) % size]

    missed = total = 0
    for body in itertools.product(odd.characters, repeat=3):
        joined = "".join(body)
        full = joined + check(joined)
        for position in range(3):
            for replacement in odd.characters:
                if replacement == full[position]:
                    continue
                total += 1
                candidate = full[:position] + replacement + full[position + 1 :]
                missed += check(candidate[:-1]) == candidate[-1]
    one_in = total / missed
    assert 35 < one_in < 50, f"1 in {one_in:.0f}"
    assert "mistake in forty" in text


def test_the_lengths_in_the_storing_table(text: str) -> None:
    scheme = Scheme()
    assert scheme.length == 8
    assert len(scheme.random()) == 9
    assert "`scheme.length` is 8" in text
    assert "`len(scheme.random())` is 9" in text


def test_the_exhaustive_substitution_count(text: str) -> None:
    """The README cites the size of the check-digit proof. Recompute it."""
    checks = len(SPOKEN) ** 3 * 3 * (len(SPOKEN) - 1)
    assert 1_200_000 < checks < 1_400_000, checks
    assert "1.3 million substitutions" in text


# --- things written as prose or tables, which running the code cannot check ---


def test_the_alphabet_listing_is_the_actual_alphabet(text: str) -> None:
    """It sat in a plain fence, so it could be replaced with vowels unnoticed."""
    assert f"```\n{SPOKEN.characters}\n```" in text


def test_the_lookalike_table_matches_the_repair_map(text: str) -> None:
    """`| `O` | `0` |` said one thing; the code is what decides."""
    shown = dict(re.findall(r"\|\s*`(\w)`\s*\|\s*`(\w)`\s*\|", text))
    assert shown, "the lookalike table was not found"
    assert shown == dict(SPOKEN.repairs), (shown, dict(SPOKEN.repairs))


def test_the_errors_table_matches_the_exception_hierarchy(text: str) -> None:

    import spokenid

    rows = re.findall(r"\|[^|\n]*\|\s*`(\w+)`\s*\|\s*`(\w+)`\s*\|", text)
    checked = 0
    for name, builtin in rows:
        error = getattr(spokenid, name, None)
        if error is None or not isinstance(error, type):
            continue
        assert issubclass(error, spokenid.SpokenIdError), name
        assert issubclass(error, getattr(builtins, builtin)), (name, builtin)
        checked += 1
    assert checked >= 4, f"only {checked} error rows were checked"


def test_the_number_of_residual_pairs_in_prose(text: str) -> None:
    assert len(SPOKEN.similar) == 6
    assert "Six pairs are still in the alphabet" in text


def test_the_column_width_in_the_storing_table(text: str) -> None:

    match = re.search(r"`varchar\((\d+)\)`", text)
    assert match, "no column width is given"
    assert int(match.group(1)) >= len(Scheme().random())


def test_the_number_of_random_characters_in_prose(text: str) -> None:
    assert Scheme().body_length == 7
    assert "carries seven random ones" in text


def test_the_survival_rate_in_prose(text: str) -> None:
    """suggest() keeps roughly one candidate in twenty-six."""
    assert len(SPOKEN) == 26
    assert "the other twenty-five in twenty-six" in text


def test_the_readme_points_people_at_column_not_position(text: str) -> None:
    """Position is a string index; column is what a person counts on a form."""
    wide = Scheme(length=10)
    repair = wide.parse("WP2-47R-P7KO").repairs[0]
    assert repair.column != repair.position
    assert "Use `repair.column` when talking to a person" in text


def test_no_link_is_relative(text: str) -> None:
    """The README is the PyPI front page, where a relative link is dead."""
    relative = [
        target
        for target in re.findall(r"\]\(([^)]+)\)", text)
        if not target.startswith(("http://", "https://", "#"))
    ]
    assert not relative, f"relative links will not resolve on PyPI: {relative}"


def test_the_changelog_has_an_unreleased_section(text: str) -> None:
    """Release-time checks live in release.yml, where the tag exists.

    They used to shell out to `git tag -l` from here, which fails in CI:
    actions/checkout does not fetch tags for a branch or pull-request build, so
    the suite saw an empty tag list and demanded the pre-release wording even
    after a release. Tagging would have turned main red permanently.
    """
    changelog = (README.parent / "CHANGELOG.md").read_text("utf-8")
    assert "## [Unreleased]" in changelog
