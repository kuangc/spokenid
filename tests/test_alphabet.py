"""The character set: what it contains, and why."""

from __future__ import annotations

import pytest

from spokenid import SPOKEN, Alphabet, InvalidScheme


def test_default_alphabet_has_no_vowels() -> None:
    assert not set(SPOKEN.characters) & set("AEIOU")


def test_default_alphabet_is_even() -> None:
    # An odd alphabet would let the Luhn check character miss single-character
    # mistakes. See tests/test_check.py::test_odd_alphabet_is_refused.
    assert len(SPOKEN) % 2 == 0


def test_default_alphabet_is_a_subset_of_crockford_base32() -> None:
    crockford = set("0123456789ABCDEFGHJKMNPQRSTVWXYZ")
    assert set(SPOKEN.characters) <= crockford


def test_no_lookalike_pair_survives_intact() -> None:
    # For every pair we know about, exactly one member is in the alphabet, so a
    # repair is always determined rather than guessed.
    for dropped, kept in SPOKEN.repairs.items():
        assert dropped not in SPOKEN.characters
        assert kept in SPOKEN.characters


def test_sorts_by_age() -> None:
    assert SPOKEN.sorts_by_age


@pytest.mark.parametrize(
    ("char", "fragment"),
    [
        ("S", "looks like '5'"),
        ("s", "looks like '5'"),
        ("A", "is a vowel"),
        ("7", "is in the alphabet"),
        ("!", "not a character this alphabet knows about"),
    ],
)
def test_explain(char: str, fragment: str) -> None:
    assert fragment in SPOKEN.explain(char)


def test_derive_without_vowel_rule_keeps_vowels() -> None:
    alphabet = Alphabet.derive(drop_vowels=False, lookalikes={})
    assert "A" in alphabet.characters


def test_derive_with_custom_lookalikes() -> None:
    alphabet = Alphabet.derive(drop_vowels=False, lookalikes={"O": "0"})
    assert "O" not in alphabet.characters
    assert alphabet.repairs == {"O": "0"}


def test_repair_target_must_be_in_the_alphabet() -> None:
    with pytest.raises(InvalidScheme, match="not in the alphabet"):
        Alphabet.derive(pool="ABC", drop_vowels=False, lookalikes={"B": "9"})


def test_repeated_character_is_refused() -> None:
    with pytest.raises(InvalidScheme, match="cannot repeat"):
        Alphabet("AAB")


def test_tiny_alphabet_is_refused() -> None:
    with pytest.raises(InvalidScheme, match="at least two"):
        Alphabet("X")


def test_membership() -> None:
    assert "7" in SPOKEN
    assert "S" not in SPOKEN
    assert "77" not in SPOKEN
    assert 7 not in SPOKEN


def test_alphabet_is_hashable() -> None:
    assert len({SPOKEN, SPOKEN}) == 1


def test_a_character_cannot_be_both_in_and_out() -> None:
    from spokenid.alphabet import Excluded

    with pytest.raises(InvalidScheme, match="both excluded and in the alphabet"):
        Alphabet("ABC", (Excluded("A", "vowel", None),))


@pytest.mark.parametrize("value", ["", "AB", "  ", 7, None])
def test_explain_handles_things_that_are_not_one_character(value: object) -> None:
    """'' used to be reported as a member, because '' in 'ABC' is True."""
    assert "not a single character" in SPOKEN.explain(value)  # type: ignore[arg-type]
