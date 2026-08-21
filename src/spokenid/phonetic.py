"""Say an identifier out loud without being misheard."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

__all__ = ["NATO", "phonetic"]

#: The NATO spelling alphabet, as used for reading letters over a radio or phone.
NATO: Mapping[str, str] = MappingProxyType(
    {
        "A": "Alfa",
        "B": "Bravo",
        "C": "Charlie",
        "D": "Delta",
        "E": "Echo",
        "F": "Foxtrot",
        "G": "Golf",
        "H": "Hotel",
        "I": "India",
        "J": "Juliett",
        "K": "Kilo",
        "L": "Lima",
        "M": "Mike",
        "N": "November",
        "O": "Oscar",
        "P": "Papa",
        "Q": "Quebec",
        "R": "Romeo",
        "S": "Sierra",
        "T": "Tango",
        "U": "Uniform",
        "V": "Victor",
        "W": "Whiskey",
        "X": "X-ray",
        "Y": "Yankee",
        "Z": "Zulu",
    }
)


def phonetic(identifier: str, separator: str = "-") -> str:
    """Spell ``identifier`` for reading aloud.

    A plain NATO speller: it does not validate, so run anything a person typed
    through :meth:`Scheme.parse` first. An empty ``separator`` spells the whole
    string as one group.

    >>> phonetic("4KM7-PC2X")
    '4 Kilo Mike 7, Papa Charlie 2 X-ray'
    >>> phonetic("4KM7", separator="")
    '4 Kilo Mike 7'
    """
    text = identifier.upper()
    groups = text.split(separator) if separator else [text]
    return ", ".join(" ".join(NATO.get(c, c) for c in group) for group in groups)
