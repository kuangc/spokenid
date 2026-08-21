"""Schemes: the shape of an identifier, and the two ways to issue one."""

from __future__ import annotations

import secrets
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field

from .alphabet import SPOKEN, Alphabet
from .check import Luhn
from .errors import InvalidScheme, SequenceExhausted, SpaceExhausted

__all__ = ["Parsed", "Repair", "Scheme"]

Taken = Callable[[str], bool]


@dataclass(frozen=True, slots=True)
class Repair:
    """One character that was read as a different one."""

    position: int
    """Index within the identifier, ignoring separators."""
    typed: str
    """What the person actually entered."""
    read_as: str
    """What it was taken to mean."""

    def __str__(self) -> str:
        return f"position {self.position}: {self.typed!r} read as {self.read_as!r}"


@dataclass(frozen=True, slots=True)
class Parsed:
    """The result of reading something a person typed."""

    ok: bool
    value: str | None = None
    """The identifier in its canonical form, or ``None`` if it could not be read."""
    repairs: tuple[Repair, ...] = ()
    """Characters that had to be reinterpreted. Empty when the input was exact."""
    problem: str | None = None
    """Why it could not be read, in a sentence you can show someone."""

    def __bool__(self) -> bool:
        return self.ok

    @property
    def exact(self) -> bool:
        """True when the input was already correct and nothing was reinterpreted."""
        return self.ok and not self.repairs


@dataclass(frozen=True)
class Scheme:
    """The shape of an identifier and the rules for issuing one.

    >>> scheme = Scheme()
    >>> scheme.first()
    '0000-0000'
    >>> scheme.next('0000-0000')
    '0000-001X'
    """

    alphabet: Alphabet = SPOKEN
    length: int = 8
    """Total characters, including the check character when there is one."""
    groups: Sequence[int] = (4, 4)
    """How to split the identifier for reading, e.g. ``(4, 4)`` for ``XXXX-XXXX``."""
    separator: str = "-"
    check: bool = True
    """Append a character that catches typing mistakes."""

    _checker: Luhn | None = field(init=False, repr=False, compare=False, default=None)

    def __post_init__(self) -> None:
        object.__setattr__(self, "groups", tuple(self.groups))
        if self.length < 2:
            raise InvalidScheme("an identifier needs at least two characters")
        if sum(self.groups) != self.length:
            raise InvalidScheme(
                f"groups {tuple(self.groups)} add up to {sum(self.groups)}, "
                f"but the identifier is {self.length} characters"
            )
        if any(size < 1 for size in self.groups):
            raise InvalidScheme("every group needs at least one character")
        if self.separator and self.separator in self.alphabet.characters:
            raise InvalidScheme(
                f"the separator {self.separator!r} is also a character in the "
                "alphabet, so an identifier could not be read back"
            )
        object.__setattr__(self, "_checker", Luhn(self.alphabet) if self.check else None)

    # ---------------------------------------------------------------- shape

    @property
    def body_length(self) -> int:
        """Characters that carry information, excluding the check character."""
        return self.length - (1 if self.check else 0)

    @property
    def space(self) -> int:
        """How many different identifiers this scheme can express."""
        # int() because a negative exponent would make ** return a float,
        # which typeshed has to allow for and mypy then widens to Any.
        return int(len(self.alphabet) ** self.body_length)

    def _group(self, flat: str) -> str:
        out = []
        start = 0
        for size in self.groups:
            out.append(flat[start : start + size])
            start += size
        return self.separator.join(out)

    def _finish(self, body: str) -> str:
        if self._checker is not None:
            body += self._checker.compute(body)
        return self._group(body)

    # ---------------------------------------------------------------- issuing

    def random(self, taken: Taken | None = None, attempts: int = 10) -> str:
        """Draw a new identifier at random.

        ``taken`` is asked whether a candidate is already in use. Supply the
        check yourself so this library never needs to know about your database::

            scheme.random(taken=lambda x: Member.objects.filter(id=x).exists())

        Raises :class:`~spokenid.SpaceExhausted` after ``attempts`` collisions in
        a row, rather than looping forever.
        """
        if attempts < 1:
            raise ValueError("attempts must be at least 1")
        chars = self.alphabet.characters
        for _ in range(attempts):
            candidate = self._finish(
                "".join(secrets.choice(chars) for _ in range(self.body_length))
            )
            if taken is None or not taken(candidate):
                return candidate
        raise SpaceExhausted(
            f"{attempts} collisions in a row drawing from {self.space:,} "
            f"identifiers. The population has outgrown this scheme; raise "
            f"Scheme(length={self.length + 1})."
        )

    def first(self) -> str:
        """The first identifier of a counted sequence."""
        return self._finish(self.alphabet.characters[0] * self.body_length)

    def next(self, previous: str, step: int = 1) -> str:
        """The identifier after ``previous``.

        Counting cannot produce a collision, so nothing needs to be looked up.
        Identifiers also sort into the order they were issued, provided the
        alphabet is in ascending order.

        ``step`` may be any positive number. Passing a random one leaves gaps,
        which makes the next identifier harder to guess while keeping both the
        ordering and the guarantee::

            scheme.next(previous, step=random.randint(1, 50))

        Raises :class:`~spokenid.SequenceExhausted` at the end of the space.
        """
        if step < 1:
            raise ValueError("step must be at least 1")
        read = self.parse(previous)
        if not read.ok or read.value is None:
            raise ValueError(f"cannot read {previous!r}: {read.problem}")
        flat = self._flatten(read.value)
        body = flat[: self.body_length]

        position = self._to_int(body) + step
        if position >= self.space:
            raise SequenceExhausted(
                f"{previous!r} is within {step} of the last identifier this "
                f"scheme can express. Raise Scheme(length={self.length + 1})."
            )
        return self._finish(self._from_int(position))

    def _to_int(self, body: str) -> int:
        chars = self.alphabet.characters
        size = len(chars)
        value = 0
        for char in body:
            value = value * size + chars.index(char)
        return value

    def _from_int(self, value: int) -> str:
        chars = self.alphabet.characters
        size = len(chars)
        out = []
        for _ in range(self.body_length):
            value, remainder = divmod(value, size)
            out.append(chars[remainder])
        return "".join(reversed(out))

    # ---------------------------------------------------------------- reading

    def _flatten(self, raw: str) -> str:
        cleaned = "".join(raw.split())
        if self.separator:
            cleaned = cleaned.replace(self.separator, "")
        return cleaned.upper()

    def parse(self, raw: str | None) -> Parsed:
        """Read something a person typed.

        Fixes case and spacing, and reinterprets any character that was dropped
        from the alphabet for looking like one that was kept. Reinterpretations
        come back in :attr:`Parsed.repairs` rather than being applied silently,
        because changing an identifier without saying so is how the wrong record
        gets opened.
        """
        if raw is None:
            return Parsed(False, problem="no identifier was given")

        flat = self._flatten(raw)
        if not flat:
            return Parsed(False, problem="no identifier was given")

        repairs: list[Repair] = []
        out: list[str] = []
        for position, char in enumerate(flat):
            if char in self.alphabet.characters:
                out.append(char)
                continue
            reads_as = self.alphabet.repairs.get(char)
            if reads_as is None:
                return Parsed(False, problem=self.alphabet.explain(char))
            repairs.append(Repair(position, char, reads_as))
            out.append(reads_as)

        fixed = "".join(out)
        if len(fixed) != self.length:
            return Parsed(
                False,
                problem=(
                    f"an identifier is {self.length} characters, "
                    f"and this one has {len(fixed)}"
                ),
            )
        if self._checker is not None and not self._checker.verify(fixed):
            return Parsed(
                False,
                problem="this is not a valid identifier; check it for a typing mistake",
            )
        return Parsed(True, self._group(fixed), tuple(repairs))

    def validate(self, raw: str | None) -> bool:
        """True when ``raw`` is already a correct identifier, needing no repair."""
        return self.parse(raw).exact

    # ---------------------------------------------------------------- sizing

    def guess_odds(self, members: int) -> float:
        """The chance that a blind guess names a real member.

        This is the number to choose ``length`` by. A repeat drawn at random is
        not a failure, because :meth:`random` simply draws again, but an
        identifier that is easy to guess is a way to reach someone else's record.
        """
        if members < 0:
            raise ValueError("members cannot be negative")
        return min(1.0, members / self.space)

    def describe(self, members: Iterable[int] = (10_000, 100_000, 1_000_000)) -> str:
        """A short report on how big this scheme is, for choosing ``length``."""
        shape = self._group("X" * self.length)
        lines = [
            f"{len(self.alphabet)}^{self.body_length} = {self.space:,} identifiers "
            f"({self.length} characters, shown as {shape})"
        ]
        for count in members:
            odds = self.guess_odds(count)
            hit = f"1 in {1 / odds:,.0f}" if odds else "never"
            lines.append(
                f"  at {count:>10,} members, a blind guess names a real one {hit}"
            )
        return "\n".join(lines)
