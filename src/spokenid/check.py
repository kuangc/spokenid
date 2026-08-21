"""The extra character on the end that catches typing mistakes."""

from __future__ import annotations

from dataclasses import dataclass

from .alphabet import Alphabet
from .errors import InvalidArgument, InvalidScheme

__all__ = ["Luhn"]


@dataclass(frozen=True, slots=True)
class Luhn:
    """A Luhn mod N check character.

    Catches every single-character mistake and most swaps of neighbouring
    characters. It only manages the first of those in an alphabet with an even
    number of characters, so an odd one is refused rather than quietly
    delivering less than it promises.

    OpenMRS ships a Luhn validator over a 25-character set today, which lets
    roughly one mistyped character in forty through unnoticed.
    """

    alphabet: Alphabet

    def __post_init__(self) -> None:
        if len(self.alphabet) % 2:
            raise InvalidScheme(
                f"a Luhn check character only catches every single-character "
                f"mistake when the alphabet has an even number of characters; "
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

    def verify(self, identifier: str) -> bool:
        """True when the last character of ``identifier`` is the right one.

        Answers ``False`` rather than raising for anything that is not made of
        alphabet characters, because callers use this as a question.
        """
        if len(identifier) < 2:
            return False
        try:
            return self.compute(identifier[:-1]) == identifier[-1]
        except InvalidArgument:
            return False
