"""Identifiers people can say out loud, write down, and type back correctly.

>>> from spokenid import Scheme
>>> scheme = Scheme()
>>> scheme.parse("o000-oooo").value
'0000-0000'
"""

from __future__ import annotations

from .alphabet import LOOKALIKES, SPOKEN, VOWELS, Alphabet, Excluded
from .check import Luhn
from .errors import (
    InvalidScheme,
    SequenceExhausted,
    SpaceExhausted,
    SpokenIdError,
)
from .phonetic import NATO, phonetic
from .scheme import Parsed, Repair, Scheme

__version__ = "0.1.0"

__all__ = [
    "LOOKALIKES",
    "NATO",
    "SPOKEN",
    "VOWELS",
    "Alphabet",
    "Excluded",
    "InvalidScheme",
    "Luhn",
    "Parsed",
    "Repair",
    "Scheme",
    "SequenceExhausted",
    "SpaceExhausted",
    "SpokenIdError",
    "__version__",
    "phonetic",
]
