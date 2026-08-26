"""Schemes: the shape of an identifier, and the two ways to issue one."""

from __future__ import annotations

import math
import secrets
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from fractions import Fraction

from .alphabet import SPOKEN, Alphabet
from .check import Luhn
from .damm import Damm
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


def _whole_number(
    value: object,
    *,
    name: str,
    minimum: int,
    maximum: int | None = None,
    error: type[InvalidArgument] | type[InvalidScheme] = InvalidArgument,
    minimum_message: str | None = None,
    maximum_message: str | None = None,
) -> int:
    """Return a bounded integer, translating Python type errors to library errors."""
    if not isinstance(value, int) or isinstance(value, bool):
        raise error(f"{name} must be a whole number, not {value!r}")
    if value < minimum:
        message = minimum_message
        if message is None:
            message = (
                f"{name} cannot be negative"
                if minimum == 0
                else f"{name} must be at least {minimum}"
            )
        raise error(message)
    if maximum is not None and value > maximum:
        raise error(maximum_message or f"{name} must be at most {maximum}")
    return value


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
    length = _whole_number(
        length,
        name="length",
        minimum=1,
        maximum=MAX_LENGTH,
    )
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
    """Its column in the raw input, counting from one.

    This includes whitespace and every separator the person entered, so it is
    the number to show them. ``position`` indexes the normalized identifier.
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


@dataclass(frozen=True, slots=True)
class _Flattened:
    """Normalized input together with where every retained symbol came from."""

    normalized: str
    typed: tuple[str, ...]
    columns: tuple[int, ...]
    truncated: bool


@dataclass(frozen=True)
class Scheme:
    """The shape of an identifier and the rules for issuing one.

    >>> scheme = Scheme()
    >>> scheme.first()
    '0000-0000'
    >>> scheme.next('0000-0000')
    '0000-0012'
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
    check: bool | Damm | Luhn = True
    """Append a character that catches typing mistakes, or use this checker."""

    _checker: Damm | Luhn | None = field(
        init=False, repr=False, compare=False, default=None
    )

    def __post_init__(self) -> None:
        # Length is checked before anything sized by it: default_groups()
        # divides by it and then builds a tuple that big, so a nonsense length
        # used to raise OverflowError or allocate gigabytes before reaching
        # the guard below.
        length = _whole_number(
            self.length,
            name="length",
            minimum=2,
            maximum=MAX_LENGTH,
            error=InvalidScheme,
            minimum_message="an identifier needs at least two characters",
            maximum_message=(
                "identifier length exceeds the supported maximum of "
                f"{MAX_LENGTH} characters"
            ),
        )
        check = self.check
        if not isinstance(check, (bool, Damm, Luhn)):
            raise InvalidScheme(
                f"check must be a boolean or a Damm or Luhn checker, not {check!r}"
            )
        if isinstance(check, (Damm, Luhn)) and check.alphabet != self.alphabet:
            raise InvalidScheme(
                "an explicit check-character checker must use the same alphabet "
                "as its Scheme"
            )
        chosen = tuple(self.groups) or default_groups(length)
        object.__setattr__(self, "groups", chosen)
        # Types before arithmetic: sum() on a group of strings raises TypeError
        # before any of the friendly messages below get a chance.
        for size in self.groups:
            _whole_number(
                size,
                name="a group size",
                minimum=1,
                error=InvalidScheme,
                minimum_message="every group needs at least one character",
            )
        if any(size > length for size in self.groups):
            raise InvalidScheme("a group cannot be longer than the whole identifier")
        if sum(self.groups) != self.length:
            raise InvalidScheme("groups must add up to the identifier length")
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
        separator_size = sum(not char.isspace() for char in self.separator)
        canonical_size = length + (len(self.groups) - 1) * separator_size
        if canonical_size > MAX_MEANINGFUL:
            raise InvalidScheme(
                f"the canonical identifier has {canonical_size} non-whitespace "
                f"characters, which is far too long to read back; the parser "
                f"accepts at most {MAX_MEANINGFUL}"
            )
        if isinstance(check, (Damm, Luhn)):
            checker: Damm | Luhn | None = check
        elif not check:
            checker = None
        elif len(self.alphabet) == 26:
            checker = Damm(self.alphabet)
        else:
            checker = Luhn(self.alphabet)
        object.__setattr__(self, "_checker", checker)

    # ---------------------------------------------------------------- shape

    @property
    def body_length(self) -> int:
        """Characters that carry information, excluding the check character."""
        return self.length - (1 if self._checker is not None else 0)

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

    def _capacity_guidance(self) -> str:
        """Name a possible next step after this identifier space runs out."""
        if self.length >= MAX_LENGTH:
            return (
                "This scheme already uses the maximum supported length; start a "
                "new identifier namespace or use a different allocation strategy."
            )
        return "Use a longer scheme with the same alphabet and checker."

    def random(self, taken: Taken | None = None, attempts: int = 10) -> str:
        """Draw a new identifier at random.

        **Without ``taken`` this can return an identifier you already issued.**
        It draws once and hands the result back; there is nothing for it to
        check against.

        ``taken`` filters candidates already known to be in use, but the check
        and return are not atomic. A database unique constraint and an insert
        retry are what guarantee uniqueness when writers can race::

            scheme.random(taken=lambda x: Member.objects.filter(id=x).exists())

        Raises :class:`~spokenid.SpaceExhausted` after ``attempts`` collisions in
        a row, rather than looping forever.
        """
        attempts = _whole_number(attempts, name="attempts", minimum=1)
        chars = self.alphabet.characters
        for _ in range(attempts):
            candidate = self._finish(
                "".join(secrets.choice(chars) for _ in range(self.body_length))
            )
            if taken is None or not taken(candidate):
                return candidate
        raise SpaceExhausted(
            f"{attempts} collisions in a row drawing from {self.space:,} "
            "identifiers. The population has outgrown this scheme. "
            f"{self._capacity_guidance()}"
        )

    def first(self) -> str:
        """The first identifier of a counted sequence."""
        return self._finish(self.alphabet.characters[0] * self.body_length)

    def next(self, previous: str, step: int = 1) -> str:
        """The identifier after ``previous``.

        Positions do not repeat within one serialized sequence. Multiple writers
        must lock or advance shared sequence state in the same transaction as
        the record insert. Identifiers sort into issue order when the alphabet
        is in ascending order.

        ``step`` may be any positive number. Varying it leaves persistent gaps
        while keeping the sequence ordered. Do not rely on gaps for secrecy or
        unpredictability: counted identifiers remain enumerable and reveal issue
        order. Use ``random()`` when identifiers should not reveal issue order.

        **Counting has a cost that is not about collisions.** Counted
        identifiers sit next to each other, so near-miss suggestions more often
        include several identifiers you issued. Persistent gaps can reduce
        overlap among those candidates; see the deterministic evaluation in
        the README.

        The default Damm check character detects every one-symbol in-alphabet
        substitution and every adjacent unequal-symbol transposition. It does
        not promise arbitrary multiple-error detection, so a valid read must
        still be matched to the right record and person.

        Raises :class:`~spokenid.Unreadable` if ``previous`` is not an
        identifier, **or if reading it needed a repair**. ``next("0000-000O")``
        refuses rather than advancing from ``"0000-0000"``, because guessing
        which identifier a sequence is at is how two records end up sharing
        one. Confirm the repaired value with :meth:`parse` and pass that.

        Raises :class:`~spokenid.SequenceExhausted` at the end of the space.
        """
        step = _whole_number(step, name="step", minimum=1)
        read = self.parse(previous)
        if not read.ok or read.value is None:
            raise Unreadable(f"cannot read the previous identifier: {read.problem}")
        if read.repairs:
            raise Unreadable(
                f"cannot advance after repairing the previous identifier to "
                f"{read.value!r}; "
                "confirm that canonical identifier and pass it again"
            )
        body = self._flatten(read.value).normalized[: self.body_length]

        position = self._to_int(body) + step
        if position >= self.space:
            raise SequenceExhausted(
                f"{read.value!r} cannot be advanced by that step without passing "
                "the last identifier this scheme can express. "
                f"{self._capacity_guidance()}"
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

    def _flatten(self, raw: str) -> _Flattened:
        """Drop whitespace and separators, and upper-case, character by character.

        Returns the cleaned text, its source characters and columns, and whether
        reading stopped early.

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
        normalized: list[str] = []
        typed: list[str] = []
        columns: list[int] = []
        truncated = False
        for column, char in enumerate(raw, start=1):
            if char.isspace():
                continue
            upper = char.upper()
            normalized.append(upper if len(upper) == 1 else char)
            typed.append(char)
            columns.append(column)
            if len(normalized) > MAX_MEANINGFUL:
                truncated = True
                break

        joined = "".join(normalized)
        if not separator:
            return _Flattened(joined, tuple(typed), tuple(columns), truncated)

        kept_normalized: list[str] = []
        kept_typed: list[str] = []
        kept_columns: list[int] = []
        position = 0
        while position < len(joined):
            if joined.startswith(separator, position):
                position += len(separator)
                continue
            kept_normalized.append(normalized[position])
            kept_typed.append(typed[position])
            kept_columns.append(columns[position])
            position += 1
        return _Flattened(
            "".join(kept_normalized),
            tuple(kept_typed),
            tuple(kept_columns),
            truncated,
        )

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

        flattened = self._flatten(raw)
        flat = flattened.normalized
        if flattened.truncated:
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
            repairs.append(
                Repair(
                    position,
                    flattened.typed[position],
                    reads_as,
                    flattened.columns[position],
                )
            )
            out.append(reads_as)

        fixed = "".join(out)
        if self._checker is not None and not self._checker.verify(fixed):
            return Parsed(
                False,
                repairs=tuple(repairs),
                problem="this is not a valid identifier; check it for a typing mistake",
            )
        return Parsed(True, self._group(fixed), tuple(repairs))

    def suggest(self, raw: object, limit: int | None = None) -> tuple[str, ...]:
        """Valid identifiers that are one small mistake away from ``raw``.

        Tries every one-symbol in-alphabet substitution, every adjacent
        unequal-symbol transposition, and one insertion or deletion when the
        length is out by one. It keeps only candidates whose check character
        agrees.

        The result may contain no candidate or several. Candidates are values
        to show and confirm, not lookup keys; submit the confirmed canonical
        value again so :attr:`Parsed.exact` is true before querying a record.

        Every candidate is returned unless you pass ``limit``. A limit removes
        candidates in generation order and can omit a correction involving the
        rightmost (check-character) position.

        >>> scheme = Scheme()
        >>> scheme.parse("0000-001W").ok          # a genuine typo
        False
        >>> "0000-0012" in scheme.suggest("0000-001W")
        True

        Returns an empty tuple when the scheme has no check character, because
        then every well-formed string is already valid and nothing is a
        near miss.
        """
        if limit is not None:
            limit = _whole_number(limit, name="limit", minimum=1)
        if self._checker is None or not isinstance(raw, str):
            return ()

        flattened = self._flatten(raw)
        flat = flattened.normalized
        if flattened.truncated:
            return ()
        table = self.alphabet.repairs
        flat = "".join(table.get(char, char) for char in flat)
        chars = self.alphabet.characters

        similar = self.alphabet.similar
        # Rank configured visual pairs before unrelated substitutions. Position
        # does not decide priority.
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

    @property
    def swap_detection(self) -> float:
        """How many neighbour swaps this scheme's check character catches.

        A fraction. The default Damm checker catches every adjacent unequal
        swap. A Scheme using Luhn may give a lower rate, depending on its
        alphabet.

        Exact rather than sampled. Damm's proven result is returned directly.
        Luhn is measured exhaustively over every one-character body at the
        minimum identifier length, or every two-character body at longer
        lengths; its rate is constant from there. Zero when there is no check
        character, because then nothing is caught.

        >>> round(Scheme().swap_detection, 3)
        1.0
        """
        checker = self._checker
        if checker is None:
            return 0.0
        if isinstance(checker, Damm):
            return 1.0
        chars = self.alphabet.characters
        caught = total = 0
        bodies: Iterable[str]
        if self.body_length == 1:
            bodies = chars
        else:
            bodies = (first + second for first in chars for second in chars)
        for body in bodies:
            full = body + checker.compute(body)
            for position in range(len(full) - 1):
                if full[position] == full[position + 1]:
                    continue
                total += 1
                swapped = (
                    full[:position]
                    + full[position + 1]
                    + full[position]
                    + full[position + 2 :]
                )
                caught += not checker.verify(swapped)
        # Only a two-symbol alphabet has no eligible unequal pair here; other
        # minimum-length Luhn identifiers have swaps that can be measured.
        return caught / total if total else 1.0

    def guess_odds(self, members: int) -> Fraction:
        """The exact chance that a uniform full-space guess names a real member.

        This assumes no knowledge of which identifiers were allocated; it is not
        an estimate of an informed guesser's success rate.

        This is one input to choosing ``length``. A repeat drawn at random must
        be rejected by an atomic database insert; separately, an identifier
        that is easy to guess should never grant access to a record.

        Returns a :class:`fractions.Fraction`, so even the largest supported
        scheme has a nonzero result for a nonzero population.
        """
        members = _whole_number(members, name="members", minimum=0)
        return Fraction(min(members, self.space), self.space)

    def describe(self, members: Iterable[int] = (10_000, 100_000, 1_000_000)) -> str:
        """A short report on scheme size and uniform full-space guessing.

        Guess odds assume no knowledge of which identifiers were allocated. A
        non-integral human-readable reciprocal is rounded to the nearest integer
        with exact integer arithmetic and labelled ``about``. Near capacity, a
        percentage keeps that rounding from collapsing a real chance into
        ``1 in 1``.
        """
        shape = self._group("X" * self.length)
        lines = [
            f"{len(self.alphabet)}^{self.body_length} = {self.space:,} identifiers "
            f"({self.length} characters, shown as {shape})"
        ]
        checker = self._checker
        if checker is not None:
            lines.append(
                f"  the {type(checker).__name__} check character detects every "
                "one-symbol in-alphabet substitution and "
                f"{self.swap_detection:.1%} of adjacent unequal-symbol transpositions"
            )
        else:
            lines.append(
                "  no check-character substitution or transposition detection; "
                "alphabet and fixed-length parsing still apply"
            )
        for count in members:
            count = _whole_number(count, name="members", minimum=0)
            if count <= 0:
                hit = "never"
                population = f"{count:>10,}"
            elif count >= self.space:
                hit = "always"
                # Do not render an attacker-sized integer. Once the population
                # fills the identifier space, the displayed odds are saturated.
                population = f"{self.space:>10,} or more"
            else:
                quotient, remainder = divmod(self.space, count)
                rounded = quotient + (2 * remainder >= count)
                if rounded == 1:
                    percent_tenths, percent_remainder = divmod(count * 1000, self.space)
                    percent_tenths += 2 * percent_remainder >= self.space
                    if percent_tenths >= 1000:
                        hit = "more than 99.9% but not always"
                    else:
                        whole, decimal = divmod(percent_tenths, 10)
                        hit = f"{whole}.{decimal}% of the time"
                elif remainder:
                    reciprocal = f"{rounded:,}" if rounded < 10**15 else _short(rounded)
                    hit = f"about 1 in {reciprocal}"
                elif quotient < 10**15:
                    hit = f"1 in {quotient:,} exactly"
                else:
                    hit = f"about 1 in {_short(quotient)}"
                population = f"{count:>10,}"
            lines.append(
                f"  at {population} members, a uniform full-space guess with no "
                f"allocation knowledge names a real one {hit}"
            )
        return "\n".join(lines)
