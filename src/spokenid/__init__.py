"""Identifiers people can say out loud, write down, and type back correctly.

>>> from spokenid import Scheme
>>> scheme = Scheme()
>>> scheme.parse("o000-oooo").value
'0000-0000'

The design is Ryan Hennig's (https://github.com/ryanhennig), written at Antara
Health in 2020 for clinicians in Kenya reading identifiers over the phone. The
repair rule follows Douglas Crockford's Base32; the shape of an issuing service
follows the OpenMRS idgen module. See the README for both.
"""

from __future__ import annotations

from .alphabet import LOOKALIKES, SIMILAR, SPOKEN, VOWELS, Alphabet, Excluded
from .check import Luhn
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
    "LOOKALIKES",
    "NATO",
    "SIMILAR",
    "SPOKEN",
    "VOWELS",
    "Alphabet",
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
