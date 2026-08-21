"""The set of characters an identifier may contain, and why each one is in it."""

from __future__ import annotations

import string
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from .errors import InvalidScheme

__all__ = ["LOOKALIKES", "SPOKEN", "VOWELS", "Alphabet", "Excluded"]

VOWELS = frozenset("AEIOU")

#: Letters that get mistaken for a digit, mapped to the digit they read as.
#: The letter is dropped and the digit kept, so a repair is never a guess.
LOOKALIKES: Mapping[str, str] = MappingProxyType(
    {"B": "8", "G": "6", "I": "1", "L": "1", "O": "0", "S": "5", "Z": "2"}
)


@dataclass(frozen=True, slots=True)
class Excluded:
    """A character that cannot appear in an identifier, and the reason."""

    char: str
    reason: str
    """Either ``"vowel"`` or ``"lookalike"``."""
    reads_as: str | None
    """The character it should be read as, or ``None`` if there is no safe answer."""


@dataclass(frozen=True, slots=True)
class Alphabet:
    """The characters an identifier may contain.

    Build one with :meth:`derive` rather than by hand, so the characters and the
    repair table are guaranteed to agree with each other.

    >>> SPOKEN.characters
    '0123456789CDFHJKMNPQRTVWXY'
    >>> SPOKEN.explain("S")
    "'S' was dropped because it looks like '5', so it reads as '5'"
    """

    characters: str
    excluded: tuple[Excluded, ...] = ()

    def __post_init__(self) -> None:
        if len(self.characters) < 2:
            raise InvalidScheme("an alphabet needs at least two characters")
        if len(set(self.characters)) != len(self.characters):
            raise InvalidScheme("an alphabet cannot repeat a character")
        for item in self.excluded:
            if item.char in self.characters:
                raise InvalidScheme(f"{item.char!r} is both excluded and in the alphabet")
            if item.reads_as is not None and item.reads_as not in self.characters:
                raise InvalidScheme(
                    f"{item.char!r} is meant to read as {item.reads_as!r}, "
                    "which is not in the alphabet"
                )

    @classmethod
    def derive(
        cls,
        *,
        drop_vowels: bool = True,
        lookalikes: Mapping[str, str] | None = None,
        pool: str = string.digits + string.ascii_uppercase,
    ) -> Alphabet:
        """Build an alphabet by removing characters from ``pool``.

        Dropping the vowels means an identifier can never spell a word, in any
        language, without anyone having to write a list of words to avoid.

        ``lookalikes`` maps a character that gets misread onto the one it should
        be read as. The key is removed and the value kept, which is what makes a
        repair certain rather than a guess.

        >>> digits_only = Alphabet.derive(pool="0123456789", lookalikes={})
        >>> digits_only.characters
        '0123456789'
        """
        table = dict(LOOKALIKES if lookalikes is None else lookalikes)
        vowels = VOWELS if drop_vowels else frozenset()

        excluded = []
        for char in pool:
            if char in vowels:
                excluded.append(Excluded(char, "vowel", table.get(char)))
            elif char in table:
                excluded.append(Excluded(char, "lookalike", table[char]))

        dropped = {item.char for item in excluded}
        characters = "".join(c for c in pool if c not in dropped)
        return cls(characters, tuple(excluded))

    def __len__(self) -> int:
        return len(self.characters)

    def __contains__(self, char: object) -> bool:
        return isinstance(char, str) and len(char) == 1 and char in self.characters

    def _excluded(self, char: str) -> Excluded | None:
        for item in self.excluded:
            if item.char == char:
                return item
        return None

    @property
    def repairs(self) -> Mapping[str, str]:
        """Excluded characters mapped to the character they should be read as."""
        return MappingProxyType(
            {i.char: i.reads_as for i in self.excluded if i.reads_as is not None}
        )

    @property
    def sorts_by_age(self) -> bool:
        """True when counted identifiers sort into the order they were issued.

        Holds when the characters are in ascending order, which makes a
        fixed-width identifier sort the same way as the number behind it.
        """
        return list(self.characters) == sorted(self.characters)

    def explain(self, char: str) -> str:
        """Say in one sentence why ``char`` is allowed, or why it is not."""
        upper = char.upper()
        if upper in self.characters:
            return f"{upper!r} is in the alphabet"
        item = self._excluded(upper)
        if item is None:
            return f"{upper!r} is not a character this alphabet knows about"
        if item.reads_as is not None:
            return (
                f"{upper!r} was dropped because it looks like "
                f"{item.reads_as!r}, so it reads as {item.reads_as!r}"
            )
        return (
            f"{upper!r} was dropped because it is a vowel, and there is no "
            "other character it could be mistaken for"
        )


#: The default alphabet: no vowels, and no letter that looks like a digit in it.
SPOKEN = Alphabet.derive()
