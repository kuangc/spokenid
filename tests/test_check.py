"""The check character, and the even-alphabet rule it depends on."""

from __future__ import annotations

import itertools
from fractions import Fraction

import pytest

from spokenid import SPOKEN, Alphabet, InvalidScheme, Luhn, Scheme


def test_luhn_documents_its_exact_alphabet_bound() -> None:
    documentation = Luhn.__doc__ or ""
    assert "every one-symbol in-alphabet substitution" in documentation
    assert "roughly" not in documentation
    assert "one in forty" not in documentation


def test_odd_alphabet_is_refused() -> None:
    odd = Alphabet.derive(lookalikes={"I": "1", "O": "0", "B": "8", "S": "5"})
    assert len(odd) % 2 == 1
    with pytest.raises(InvalidScheme, match="even number of characters"):
        Luhn(odd)


def test_catches_every_single_character_mistake() -> None:
    """The promise Luhn exists to make, proved rather than asserted.

    Exhaustive over every three-character body and every substitution, including
    the check character: 26^3 * 4 * 25 = 1.75M checks.
    """
    luhn = Luhn(SPOKEN)
    chars = SPOKEN.characters
    missed = 0
    total = 0
    for body in itertools.product(chars, repeat=3):
        original = "".join(body) + luhn.compute("".join(body))
        for position in range(len(original)):
            for replacement in chars:
                if replacement == original[position]:
                    continue
                total += 1
                candidate = original[:position] + replacement + original[position + 1 :]
                if luhn.verify(candidate):
                    missed += 1
    assert total > 1_700_000
    assert missed == 0


def luhn_swap_counts(body_length: int) -> tuple[int, int]:
    luhn = Luhn(SPOKEN)
    chars = SPOKEN.characters
    caught = total = 0
    for body in itertools.product(chars, repeat=body_length):
        original = "".join(body) + luhn.compute("".join(body))
        for position in range(len(original) - 1):
            if original[position] == original[position + 1]:
                continue
            total += 1
            candidate = (
                original[:position]
                + original[position + 1]
                + original[position]
                + original[position + 2 :]
            )
            caught += not luhn.verify(candidate)
    return caught, total


@pytest.mark.parametrize("body_length", [2, 3])
def test_catches_a_pinned_fraction_of_neighbour_swaps(body_length: int) -> None:
    caught, total = luhn_swap_counts(body_length)
    assert Fraction(caught, total) == Fraction(1296, 1300)


def test_catches_every_neighbour_swap_at_minimum_length() -> None:
    caught, total = luhn_swap_counts(1)
    assert (caught, total) == (24, 24)


@pytest.mark.parametrize("short", ["", "0", "4"])
def test_verify_rejects_something_too_short(short: str) -> None:
    """A lone "4" does not reveal a missing guard, but "0" and "" do.

    Without the length check, verify("0") compares compute("") to "0" and
    answers True, and verify("") raises IndexError.
    """
    assert not Luhn(SPOKEN).verify(short)


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


@pytest.mark.parametrize("junk", [None, b"0000000X", 12345, ["0", "0"], 3.5])
def test_verify_answers_for_things_that_are_not_text(junk: object) -> None:
    """It promises a bool, so it has to return one for anything at all."""
    assert Luhn(SPOKEN).verify(junk) is False


def test_swap_detection_is_exact_not_sampled() -> None:
    """The rate does not change with length, so a short measurement is exact."""
    luhn = Luhn(SPOKEN)
    scheme = Scheme(check=luhn)
    caught = total = 0
    for body in itertools.product(SPOKEN.characters, repeat=3):
        joined = "".join(body)
        full = joined + luhn.compute(joined)
        for position in range(len(full) - 1):
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
    assert abs(scheme.swap_detection - caught / total) < 1e-12


def test_scheme_reports_luhns_minimum_length_special_case() -> None:
    assert Scheme(length=2, check=Luhn(SPOKEN)).swap_detection == 1.0


def test_luhn_reports_vacuous_swap_detection_for_a_two_symbol_alphabet() -> None:
    binary = Alphabet("01")
    assert Scheme(alphabet=binary, length=2, check=Luhn(binary)).swap_detection == 1.0


def test_no_check_character_catches_nothing() -> None:
    assert Scheme(check=False).swap_detection == 0.0


def test_describe_reports_the_rate() -> None:
    assert "Damm check character" in Scheme().describe([1000])
    assert (
        "detects every one-symbol in-alphabet substitution and 100.0% of adjacent "
        "unequal-symbol transpositions" in Scheme().describe([1000])
    )
    luhn_report = Scheme(check=Luhn(SPOKEN)).describe([1000])
    assert "Luhn check character" in luhn_report
    assert "99.7% of adjacent unequal-symbol transpositions" in luhn_report
    no_check_report = Scheme(check=False).describe([1000])
    assert "no check character, so no mistake is caught" not in no_check_report
    assert (
        "no check-character substitution or transposition detection; alphabet "
        "and fixed-length parsing still apply" in no_check_report
    )
