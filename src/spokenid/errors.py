"""Exceptions raised by spokenid."""

from __future__ import annotations

__all__ = [
    "InvalidScheme",
    "SequenceExhausted",
    "SpaceExhausted",
    "SpokenIdError",
]


class SpokenIdError(Exception):
    """Base class for every error this library raises."""


class InvalidScheme(SpokenIdError, ValueError):
    """A :class:`~spokenid.Scheme` was asked for something it cannot be."""


class SpaceExhausted(SpokenIdError, RuntimeError):
    """Random drawing kept colliding, so the space is too small for the population."""


class SequenceExhausted(SpokenIdError, RuntimeError):
    """``Scheme.next()`` ran past the last identifier the scheme can express."""
