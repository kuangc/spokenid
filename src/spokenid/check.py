"""The extra character on the end that catches typing mistakes."""

from __future__ import annotations

from dataclasses import dataclass

from .alphabet import Alphabet
from .errors import InvalidArgument, InvalidScheme

__all__ = ["Luhn"]


@dataclass(frozen=True, slots=True)
class Luhn:
    """A Luhn mod N check character.

    Over an even-sized alphabet, detects every one-symbol in-alphabet substitution
    and a checker-dependent fraction of adjacent unequal-symbol transpositions.
    The substitution guarantee does not hold for an odd-sized alphabet, so an odd
    alphabet is refused rather than quietly weakening the contract.
    """

    alphabet: Alphabet

    def __post_init__(self) -> None:
        if len(self.alphabet) % 2:
            raise InvalidScheme(
                "a Luhn check character only detects every one-symbol in-alphabet "
                "substitution when the alphabet has an even number of characters; "
                f"this one has {len(self.alphabet)}. Add or remove a character, "
                f"or build the Scheme with check=False."
            )

    def compute(self, body: str) -> str:
        """Return the check character for ``body``.

        Raises :class:`~spokenid.InvalidArgument` if ``body`` contains anything
        outside the alphabet.
        """
        chars = self.alphabet.characters
        size = len(chars)
        factor = 2
        total = 0
        for char in reversed(body):
            position = chars.find(char)
            if position < 0:
                raise InvalidArgument(
                    f"{char!r} is not in the alphabet, so it has no check character"
                )
            addend = factor * position
            factor = 1 if factor == 2 else 2
            total += addend // size + addend % size
        return chars[(size - total % size) % size]

    def verify(self, identifier: object) -> bool:
        """True when the last character of ``identifier`` is the right one.

        Answers ``False`` rather than raising for anything that is not made of
        alphabet characters, because callers use this as a question.
        """
        if not isinstance(identifier, str) or len(identifier) < 2:
            return False
        try:
            return self.compute(identifier[:-1]) == identifier[-1]
        except InvalidArgument:
            return False
