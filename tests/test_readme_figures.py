"""Numbers written in the README prose, checked against the code.

The README's persuasive power rests on its figures being exactly right, and a
figure in a sentence is not caught by running the code blocks. Each one here is
derived from the library and then required to appear in the text, so neither can
drift without a failure.
"""

from __future__ import annotations

import itertools
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
