"""The check character, and the even-alphabet rule it depends on."""

from __future__ import annotations

import itertools

import pytest

from spokenid import SPOKEN, Alphabet, InvalidScheme, Luhn


def test_odd_alphabet_is_refused() -> None:
    odd = Alphabet.derive(lookalikes={"I": "1", "O": "0", "B": "8", "S": "5"})
    assert len(odd) % 2 == 1
    with pytest.raises(InvalidScheme, match="even number of characters"):
        Luhn(odd)


def test_check_character_verifies() -> None:
    luhn = Luhn(SPOKEN)
    assert luhn.verify("4KM7PC2" + luhn.compute("4KM7PC2"))


def test_catches_every_single_character_mistake() -> None:
    """The promise Luhn exists to make, proved rather than asserted.

    Exhaustive over every three-character body and every substitution, which is
    26^3 * 3 * 25 = 1.3M checks. An odd alphabet lets roughly 1 in 40 through.
    """
    luhn = Luhn(SPOKEN)
    chars = SPOKEN.characters
    missed = 0
    total = 0
    for body in itertools.product(chars, repeat=3):
        original = "".join(body) + luhn.compute("".join(body))
        for position in range(3):
            for replacement in chars:
                if replacement == original[position]:
                    continue
                total += 1
                candidate = original[:position] + replacement + original[position + 1 :]
                if luhn.verify(candidate):
                    missed += 1
    assert total > 1_000_000
    assert missed == 0


def test_catches_most_neighbour_swaps() -> None:
    luhn = Luhn(SPOKEN)
    chars = SPOKEN.characters
    missed = 0
    total = 0
    for body in itertools.product(chars, repeat=3):
        original = "".join(body) + luhn.compute("".join(body))
        for position in range(2):
            if original[position] == original[position + 1]:
                continue
            total += 1
            candidate = (
                original[:position]
                + original[position + 1]
                + original[position]
                + original[position + 2 :]
            )
            if luhn.verify(candidate):
                missed += 1
    # Luhn does not promise every swap, only most of them. Hold the line where
    # it actually sits so a regression shows up.
    assert missed / total < 0.01


def test_verify_rejects_something_too_short() -> None:
    assert not Luhn(SPOKEN).verify("4")


def test_verify_answers_rather_than_raising_on_junk() -> None:
    """It returns a bool, so it has to return one for anything."""
    luhn = Luhn(SPOKEN)
    assert not luhn.verify("AAAA")
    assert not luhn.verify("0-0")
    assert not luhn.verify("ßß")


def test_compute_refuses_a_character_it_does_not_know() -> None:
    from spokenid import InvalidArgument

    with pytest.raises(InvalidArgument, match="not in the alphabet"):
        Luhn(SPOKEN).compute("A")
