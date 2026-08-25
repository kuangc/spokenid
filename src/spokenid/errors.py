"""Exceptions raised by spokenid.

Everything this library raises inherits from :class:`SpokenIdError`, and also
from the built-in you would expect, so existing ``except`` clauses keep working.
"""

from __future__ import annotations

__all__ = [
    "InvalidArgument",
    "InvalidScheme",
    "SequenceExhausted",
    "SpaceExhausted",
    "SpokenIdError",
    "Unreadable",
]


class SpokenIdError(Exception):
    """Base class for every error this library raises."""


class InvalidScheme(SpokenIdError, ValueError):
    """A :class:`~spokenid.Scheme` or :class:`~spokenid.Alphabet` cannot exist."""


class InvalidArgument(SpokenIdError, ValueError):
    """An argument to a method was outside what it accepts."""


class Unreadable(SpokenIdError, ValueError):
    """Something that should have been an identifier could not be read."""


class SpaceExhausted(SpokenIdError, RuntimeError):
    """Random drawing kept colliding, so the space is too small for the population."""


class SequenceExhausted(SpokenIdError, RuntimeError):
    """``Scheme.next()`` ran past the last identifier the scheme can express."""
