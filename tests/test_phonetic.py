"""Reading an identifier out loud."""

from __future__ import annotations

from spokenid import NATO, SPOKEN, phonetic


def test_accepts_lowercase() -> None:
    assert phonetic("4km7-pc2x") == phonetic("4KM7-PC2X")


def test_every_letter_in_the_alphabet_has_a_word() -> None:
    letters = [c for c in SPOKEN.characters if c.isalpha()]
    assert letters
    assert all(c in NATO for c in letters)


def test_a_character_with_no_word_is_spoken_as_itself() -> None:
    assert phonetic("4K", words={}) == "4 K"
