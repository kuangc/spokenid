"""Generate and read short identifiers intended for spoken use.

>>> from spokenid import Scheme
>>> scheme = Scheme()
>>> scheme.parse("0000-0000").value
'0000-0000'

This package is an independent Python implementation of an identifier design
credited to Ryan Hennig and Antara Health. See the README for its scope,
cautions, source notes, and historical details that still require confirmation.
"""

from __future__ import annotations

from .alphabet import LOOKALIKES, SIMILAR, SPOKEN, VOWELS, Alphabet, Excluded
from .check import Luhn
from .damm import DAMM_26_TABLE, Damm
from .errors import (
    InvalidArgument,
    InvalidScheme,
    SequenceExhausted,
    SpaceExhausted,
    SpokenIdError,
    Unreadable,
)
from .phonetic import NATO, phonetic
from .scheme import Parsed, Repair, Scheme, default_groups

__version__ = "0.1.0"

__all__ = [
    "DAMM_26_TABLE",
    "LOOKALIKES",
    "NATO",
    "SIMILAR",
    "SPOKEN",
    "VOWELS",
    "Alphabet",
    "Damm",
    "Excluded",
    "InvalidArgument",
    "InvalidScheme",
    "Luhn",
    "Parsed",
    "Repair",
    "Scheme",
    "SequenceExhausted",
    "SpaceExhausted",
    "SpokenIdError",
    "Unreadable",
    "__version__",
    "default_groups",
    "phonetic",
]
