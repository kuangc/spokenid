"""Exceptions raised by spokenid.

Domain errors inherit from :class:`SpokenIdError` and a conventional built-in,
so existing ``except`` clauses keep working. Misusing ``Parsed`` in a boolean
context raises the built-in :class:`TypeError` instead.
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
    """Base class for the library's domain errors."""


class InvalidScheme(SpokenIdError, ValueError):
    """A :class:`~spokenid.Scheme` or :class:`~spokenid.Alphabet` cannot exist."""


class InvalidArgument(SpokenIdError, ValueError):
    """An argument to a method was outside what it accepts."""


class Unreadable(SpokenIdError, ValueError):
    """Something that should have been an identifier could not be read."""


class SpaceExhausted(SpokenIdError, RuntimeError):
    """Random drawing exhausted its retry budget, not necessarily the space."""


class SequenceExhausted(SpokenIdError, RuntimeError):
    """``Scheme.next()`` ran past the last identifier the scheme can express."""
