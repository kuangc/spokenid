"""Schemes: the shape of an identifier, and the two ways to issue one."""

from __future__ import annotations

import math
import secrets
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field

from .alphabet import SPOKEN, Alphabet
from .check import Luhn
from .errors import (
    InvalidArgument,
    InvalidScheme,
    SequenceExhausted,
    SpaceExhausted,
    Unreadable,
)

__all__ = ["Parsed", "Repair", "Scheme"]

Taken = Callable[[str], bool]

#: Characters per group when the caller does not choose. Four reads well aloud.
PREFERRED_GROUP = 4

#: How many non-whitespace characters reading will look at, separators
#: included. Far past any identifier, and it stops a pasted megabyte being
#: scanned in full. Beyond it, reading refuses rather than truncating.
MAX_MEANINGFUL = 4096

#: Longest identifier a scheme may describe. Far past anything a person would
#: read aloud, and it keeps the arithmetic inside what str() will format:
#: Python refuses to render an integer of more than 4300 digits.
MAX_LENGTH = 256


def _short(value: int) -> str:
    """Approximate a very large integer without converting it to a float.

    ``float(10**400)`` overflows, so the digits are counted instead.
    """
    digits = str(value)
    fraction = digits[1:3].ljust(2, "0")
    return f"{digits[0]}.{fraction}e+{len(digits) - 1}"


def default_groups(length: int) -> tuple[int, ...]:
    """Split ``length`` into even-sized groups of about four characters.

    >>> default_groups(8)
    (4, 4)
    >>> default_groups(7)
    (3, 4)
    >>> default_groups(10)
    (3, 3, 4)
    """
    if length <= 5:
        return (length,)
    count = math.ceil(length / PREFERRED_GROUP)
    base, extra = divmod(length, count)
    return tuple(base + (1 if i >= count - extra else 0) for i in range(count))


@dataclass(frozen=True, slots=True)
class Repair:
    """One character that was read as a different one."""

    position: int
    """Index into the identifier, counting from zero and ignoring separators."""
    typed: str
    """What the person actually entered."""
    read_as: str
    """What it was taken to mean."""
    column: int = 0
    """Which character it is when written out, counting from one, separators included.

    This is the number to show a person. ``position`` is for indexing; a clerk
    looking at ``WP2-47R-P7KO`` on a form counts the ``O`` as the twelfth
    character, not the ninth.
    """

    def __str__(self) -> str:
        return f"character {self.column}: {self.typed!r} read as {self.read_as!r}"


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
    groups: Sequence[int] = ()
    """How to split the identifier for reading, e.g. ``(4, 4)`` for ``XXXX-XXXX``.

    Left empty, it follows ``length`` in groups of about four. After a scheme is
    built this is always a filled tuple, never empty.
    """
    separator: str = "-"
    check: bool = True
    """Append a character that catches typing mistakes."""

    _checker: Luhn | None = field(init=False, repr=False, compare=False, default=None)

    def __post_init__(self) -> None:
        # Length is checked before anything sized by it: default_groups()
        # divides by it and then builds a tuple that big, so a nonsense length
        # used to raise OverflowError or allocate gigabytes before reaching
        # the guard below.
        if not isinstance(self.length, int) or isinstance(self.length, bool):
            raise InvalidScheme(f"length must be a whole number, not {self.length!r}")
        if self.length < 2:
            raise InvalidScheme("an identifier needs at least two characters")
        if self.length > MAX_LENGTH:
            raise InvalidScheme(
                f"an identifier of {self.length} characters is past the {MAX_LENGTH} "
                "this handles, and nobody could read it aloud anyway"
            )
        chosen = tuple(self.groups) or default_groups(self.length)
        object.__setattr__(self, "groups", chosen)
        # Types before arithmetic: sum() on a group of strings raises TypeError
        # before any of the friendly messages below get a chance.
        for size in self.groups:
            if not isinstance(size, int) or isinstance(size, bool):
                raise InvalidScheme(f"a group size must be a whole number, not {size!r}")
            if size < 1:
                raise InvalidScheme("every group needs at least one character")
        if sum(self.groups) != self.length:
            raise InvalidScheme(
                f"groups {tuple(self.groups)} add up to {sum(self.groups)}, "
                f"but the identifier is {self.length} characters"
            )
        # The separator has to survive reading, which upper-cases and strips
        # whitespace. Compare the folded form, or a lower-case separator passes
        # here and then deletes a body character in _flatten.
        folded = self.separator.upper()
        if len(folded) != len(self.separator):
            raise InvalidScheme(
                f"the separator {self.separator!r} changes length when upper-cased, "
                "so an identifier could not be read back"
            )
        mixes_whitespace = (
            self.separator
            and not self.separator.isspace()
            and any(char.isspace() for char in self.separator)
        )
        if mixes_whitespace:
            raise InvalidScheme(
                f"the separator {self.separator!r} mixes whitespace with other "
                "characters, and reading strips whitespace first"
            )
        # `in` on a str is a substring test: "YX" would pass while "XY" failed.
        # Include the characters that repair into the alphabet, or a typed
        # separator would be stripped instead of corrected.
        clash = set(folded) & (set(self.alphabet.characters) | set(self.alphabet.repairs))
        if clash:
            raise InvalidScheme(
                f"the separator {self.separator!r} uses {''.join(sorted(clash))!r}, "
                "which the alphabet already means something by, so an identifier "
                "could not be read back"
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

    def _column(self, position: int) -> int:
        """Where ``position`` falls in the written form, counting from one."""
        seen = 0
        for group_number, size in enumerate(self.groups):
            if position < seen + size:
                return position + 1 + group_number * len(self.separator)
            seen += size
        return position + 1

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
            raise InvalidArgument("attempts must be at least 1")
        chars = self.alphabet.characters
        for _ in range(attempts):
            candidate = self._finish(
                "".join(secrets.choice(chars) for _ in range(self.body_length))
            )
            if taken is None or not taken(candidate):
                return candidate
        raise SpaceExhausted(
            f"{attempts} collisions in a row drawing from {self.space:,} "
            f"identifiers. The population has outgrown this scheme; use a "
            f"longer one, such as Scheme(length={self.length + 1})."
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

        This assumes one writer. Two processes that read the same stored value
        both get the same answer, so whatever holds the last issued identifier
        has to serialise access to it, with a row lock or a single sequence.

        Raises :class:`~spokenid.Unreadable` if ``previous`` is not an
        identifier, and :class:`~spokenid.SequenceExhausted` at the end.
        """
        if step < 1:
            raise InvalidArgument("step must be at least 1")
        read = self.parse(previous)
        if not read.ok or read.value is None:
            raise Unreadable(f"cannot read {previous!r}: {read.problem}")
        flat, _ = self._flatten(read.value)
        body = flat[: self.body_length]

        position = self._to_int(body) + step
        if position >= self.space:
            raise SequenceExhausted(
                f"{previous!r} is within {step} of the last identifier this "
                f"scheme can express. Use a longer one, such as "
                f"Scheme(length={self.length + 1})."
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

    def _flatten(self, raw: str) -> tuple[str, bool]:
        """Drop whitespace and separators, and upper-case, character by character.

        Returns the cleaned text and whether reading stopped early.

        One character at a time because ``str.upper()`` can lengthen a string
        (``"ß"`` becomes ``"SS"``), which would report mistakes at positions the
        person never typed.

        Reading stops after :data:`MAX_MEANINGFUL` non-whitespace characters,
        separators included, and says so rather than pretending the rest was
        not there. An earlier version stopped without saying, so
        ``"0000-001X --- Jane Doe"`` shed its tail and was accepted as
        ``"0000-001X"``, which is the exact failure this library exists to
        prevent.
        """
        separator = self.separator.upper()
        kept: list[str] = []
        truncated = False
        for char in raw:
            if char.isspace():
                continue
            upper = char.upper()
            kept.append(upper if len(upper) == 1 else char)
            if len(kept) > MAX_MEANINGFUL:
                truncated = True
                break
        cleaned = "".join(kept)
        if separator:
            cleaned = cleaned.replace(separator, "")
        return cleaned, truncated

    def parse(self, raw: object) -> Parsed:
        """Read something a person typed.

        Fixes case and spacing, and reinterprets any character that was dropped
        from the alphabet for looking like one that was kept. Reinterpretations
        come back in :attr:`Parsed.repairs` rather than being applied silently,
        because changing an identifier without saying so is how the wrong record
        gets opened.
        """
        if raw is None:
            return Parsed(False, problem="no identifier was given")
        if not isinstance(raw, str):
            return Parsed(
                False,
                problem=(f"an identifier is text, and this is {type(raw).__name__}"),
            )

        flat, truncated = self._flatten(raw)
        if truncated:
            return Parsed(
                False,
                problem="this is far too long to be an identifier",
            )
        if not flat:
            return Parsed(False, problem="no identifier was given")
        # Length first. Repairs are one character for one character, so this
        # cannot change, and checking now bounds the work on a long paste.
        if len(flat) != self.length:
            return Parsed(
                False,
                problem=(
                    f"an identifier is {self.length} characters, "
                    f"and this one has {len(flat)}"
                ),
            )

        allowed = self.alphabet.characters
        table = self.alphabet.repairs  # a fresh mapping per access, so read it once
        repairs: list[Repair] = []
        out: list[str] = []
        for position, char in enumerate(flat):
            if char in allowed:
                out.append(char)
                continue
            reads_as = table.get(char)
            if reads_as is None:
                return Parsed(False, problem=self.alphabet.explain(char))
            repairs.append(Repair(position, char, reads_as, self._column(position)))
            out.append(reads_as)

        fixed = "".join(out)
        if self._checker is not None and not self._checker.verify(fixed):
            return Parsed(
                False,
                problem="this is not a valid identifier; check it for a typing mistake",
            )
        return Parsed(True, self._group(fixed), tuple(repairs))

    def suggest(self, raw: object, limit: int | None = None) -> tuple[str, ...]:
        """Valid identifiers that are one small mistake away from ``raw``.

        For when :meth:`parse` says no and somebody is standing at the counter.
        Tries every single-character substitution, every swap of neighbouring
        characters, and one insertion or deletion if the length is out by one,
        keeping only the results whose check character agrees.

        The check character is what makes this short: out of every string one
        edit away, only about one in twenty-six survives, so the answer is a
        handful of candidates rather than a haystack, roughly one per character.
        Look them up: the identifier that was meant is always among them.

        How many of them you also hold depends on how you issue. Drawn at
        random, it is essentially always exactly one. Counted with ``step=1``,
        neighbours are dense, so at a thousand members about a third of the
        time two or three of the candidates are yours and the person has to be
        asked which. Counting with gaps takes that back to about one in twenty.

        Every candidate is returned unless you pass ``limit``. Cutting the list
        short is a bad trade: the substitutions are generated left to right, so
        a limit drops the rightmost position first, and the rightmost position
        is the check character, which is one of the likeliest things to mistype.

        >>> scheme = Scheme()
        >>> scheme.parse("0000-001W").ok          # a genuine typo
        False
        >>> "0000-001X" in scheme.suggest("0000-001W")
        True

        Returns an empty tuple when the scheme has no check character, because
        then every well-formed string is already valid and nothing is a
        near miss.
        """
        if limit is not None and limit < 1:
            raise InvalidArgument("limit must be at least 1")
        if self._checker is None or not isinstance(raw, str):
            return ()

        flat, truncated = self._flatten(raw)
        if truncated:
            return ()
        table = self.alphabet.repairs
        flat = "".join(table.get(char, char) for char in flat)
        chars = self.alphabet.characters

        similar = self.alphabet.similar
        # Rank by how likely the mistake was, not by where it sits in the
        # string: a character swapped for one that looks like it beats a
        # character swapped for an unrelated one.
        found: dict[str, int] = {}

        def keep(candidate: str, rank: int) -> None:
            if len(candidate) != self.length or self._checker is None:
                return
            if candidate == flat or not self._checker.verify(candidate):
                return
            grouped = self._group(candidate)
            if rank < found.get(grouped, rank + 1):
                found[grouped] = rank

        if len(flat) == self.length:
            for position in range(self.length):
                typed = flat[position]
                for replacement in chars:
                    if replacement == typed:
                        continue
                    looks_alike = frozenset((typed, replacement)) in similar
                    keep(
                        flat[:position] + replacement + flat[position + 1 :],
                        0 if looks_alike else 2,
                    )
            for position in range(self.length - 1):
                if flat[position] != flat[position + 1]:
                    keep(
                        flat[:position]
                        + flat[position + 1]
                        + flat[position]
                        + flat[position + 2 :],
                        1,
                    )
        elif len(flat) == self.length - 1:
            for position in range(len(flat) + 1):
                for extra in chars:
                    keep(flat[:position] + extra + flat[position:], 1)
        elif len(flat) == self.length + 1:
            for position in range(len(flat)):
                keep(flat[:position] + flat[position + 1 :], 1)

        ranked = sorted(found, key=lambda candidate: found[candidate])
        return tuple(ranked if limit is None else ranked[:limit])

    def validate(self, raw: object) -> bool:
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
            raise InvalidArgument("members cannot be negative")
        if members >= self.space:
            return 1.0
        # Compared before dividing: members / space overflows for a huge
        # population, and underflows to 0.0 for a huge space.
        return members / self.space

    def describe(self, members: Iterable[int] = (10_000, 100_000, 1_000_000)) -> str:
        """A short report on how big this scheme is, for choosing ``length``."""
        shape = self._group("X" * self.length)
        lines = [
            f"{len(self.alphabet)}^{self.body_length} = {self.space:,} identifiers "
            f"({self.length} characters, shown as {shape})"
        ]
        for count in members:
            if count < 0:
                raise InvalidArgument("members cannot be negative")
            # Integer division, because the float form underflows to zero for a
            # large space and then reports a finite risk as "never".
            if count <= 0:
                hit = "never"
            elif count >= self.space:
                hit = "always"
            else:
                one_in = self.space // count
                hit = f"1 in {one_in:,}" if one_in < 10**15 else f"1 in {_short(one_in)}"
            lines.append(
                f"  at {count:>10,} members, a blind guess names a real one {hit}"
            )
        return "\n".join(lines)
