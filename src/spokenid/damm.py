"""A Damm check character over the default 26-symbol alphabet."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from .alphabet import Alphabet
from .errors import InvalidArgument, InvalidScheme

__all__ = ["DAMM_26_TABLE", "Damm"]

DammTable = tuple[tuple[int, ...], ...]

_FIELD_CHARACTERISTIC = 5
_ALPHA = 3 + 5 * 3
_BETA = 3 + 5 * 2


def _field_add(left: int, right: int) -> int:
    """Add encoded elements of ``F5[s] / (s^2 - 2)``."""
    real = (left % 5 + right % 5) % _FIELD_CHARACTERISTIC
    unreal = (left // 5 + right // 5) % _FIELD_CHARACTERISTIC
    return real + 5 * unreal


def _field_multiply(left: int, right: int) -> int:
    """Multiply encoded elements of ``F5[s] / (s^2 - 2)``."""
    left_real, left_unreal = left % 5, left // 5
    right_real, right_unreal = right % 5, right // 5
    real = (
        left_real * right_real + 2 * left_unreal * right_unreal
    ) % _FIELD_CHARACTERISTIC
    unreal = (left_real * right_unreal + left_unreal * right_real) % _FIELD_CHARACTERISTIC
    return real + 5 * unreal


def _star(left: int, right: int) -> int:
    """The order-25 quasigroup operation before prolongation."""
    return _field_add(
        _field_add(_field_multiply(_ALPHA, left), _field_multiply(_BETA, right)),
        1,
    )


def _prolonged(left: int, right: int) -> int:
    """Apply Damm's prolongation with infinity relabelled as zero."""
    if left == right:
        return 0
    if left == 0:
        field = right - 1
        return _star(field, field) + 1
    if right == 0:
        field = left - 1
        return _star(field, field) + 1
    return _star(left - 1, right - 1) + 1


def _build_damm_26_table() -> DammTable:
    """Build the persisted order-26 table from its finite-field construction."""
    return tuple(
        tuple(_prolonged(row, column) for column in range(26)) for row in range(26)
    )


#: The frozen order-26 quasigroup used by the default alphabet.
DAMM_26_TABLE: DammTable = _build_damm_26_table()


def _canonical_table(
    supplied: Iterable[Iterable[int]],
    size: int,
) -> DammTable:
    """Copy and validate a caller-supplied quasigroup table."""
    try:
        table = tuple(tuple(row) for row in supplied)
    except TypeError as exc:
        raise InvalidScheme("a Damm table must be an iterable of rows") from exc

    if len(table) != size:
        raise InvalidScheme(
            f"a Damm table for this alphabet needs exactly {size} rows, not {len(table)}"
        )
    for row_number, row in enumerate(table):
        if len(row) != size:
            raise InvalidScheme(
                f"row {row_number} of a Damm table needs exactly {size} entries, "
                f"not {len(row)}"
            )

    for row in table:
        for value in row:
            if not isinstance(value, int) or isinstance(value, bool):
                raise InvalidScheme("Damm table entries must be integers, not booleans")
            if not 0 <= value < size:
                raise InvalidScheme(
                    f"Damm table entries must be between 0 and {size - 1}"
                )

    expected = set(range(size))
    for row_number, row in enumerate(table):
        if set(row) != expected:
            raise InvalidScheme(
                f"row {row_number} of a Damm table must contain every table "
                "value exactly once"
            )
    for column in range(size):
        if {table[row][column] for row in range(size)} != expected:
            raise InvalidScheme(
                f"column {column} of a Damm table must contain every table "
                "value exactly once"
            )

    for index in range(size):
        if table[index][index] != 0:
            raise InvalidScheme(f"diagonal entry {index} of a Damm table must be zero")

    for state in range(size):
        for first in range(size):
            state_first = table[state][first]
            for second in range(first + 1, size):
                if table[state_first][second] == table[table[state][second]][first]:
                    raise InvalidScheme(
                        "a Damm table must be weakly totally anti-symmetric"
                    )
    return table


@dataclass(frozen=True, slots=True, init=False)
class Damm:
    """A Damm check character backed by a validated quasigroup table.

    Without an explicit ``table``, the bundled construction is available for
    26-character alphabets. Other alphabet sizes require a complete custom
    table whose error-detection properties are checked before it is accepted.
    """

    alphabet: Alphabet
    table: DammTable = field(repr=False)

    def __init__(
        self,
        alphabet: Alphabet,
        table: Iterable[Iterable[int]] | None = None,
    ) -> None:
        object.__setattr__(self, "alphabet", alphabet)
        if table is None:
            if len(alphabet) != 26:
                raise InvalidScheme(
                    "the bundled Damm table is only for a 26-character alphabet; "
                    "supply a custom table for this one"
                )
            table = DAMM_26_TABLE
        object.__setattr__(self, "table", _canonical_table(table, len(alphabet)))

    def compute(self, body: str) -> str:
        """Return the check character for ``body``.

        Raises :class:`~spokenid.InvalidArgument` if ``body`` contains anything
        outside the alphabet.
        """
        state = 0
        chars = self.alphabet.characters
        for char in body:
            position = chars.find(char)
            if position < 0:
                raise InvalidArgument(
                    f"{char!r} is not in the alphabet, so it has no check character"
                )
            state = self.table[state][position]
        return chars[state]

    def verify(self, identifier: object) -> bool:
        """True when ``identifier`` ends with its Damm check character."""
        if not isinstance(identifier, str) or len(identifier) < 2:
            return False
        try:
            return self.compute(identifier[:-1]) == identifier[-1]
        except InvalidArgument:
            return False
