"""The frozen order-26 Damm quasigroup and the errors it detects."""

from __future__ import annotations

import hashlib
import itertools
from collections.abc import Callable
from typing import Any

import pytest

from spokenid import (
    DAMM_26_TABLE,
    SPOKEN,
    Alphabet,
    Damm,
    InvalidArgument,
    InvalidScheme,
)


def test_golden_vectors() -> None:
    checker = Damm(SPOKEN)
    assert checker.compute("0000000") == "0"
    assert checker.compute("0000001") == "2"
    assert checker.verify("00000012")
    assert not checker.verify("0000001X")


def test_frozen_table_digest_uses_row_major_bytes() -> None:
    raw = bytes(value for row in DAMM_26_TABLE for value in row)
    assert hashlib.sha256(raw).hexdigest() == (
        "a0610f93f3294c2a271d3bc2f84dc5a84ffcea024c6c5eb7cd7ea996f7afa144"
    )


def test_first_four_six_symbol_identifiers_are_stable() -> None:
    checker = Damm(SPOKEN)

    def finish(body: str) -> str:
        flat = body + checker.compute(body)
        return f"{flat[:3]}-{flat[3:]}"

    assert tuple(finish(f"{number:05d}") for number in range(4)) == (
        "000-000",
        "000-012",
        "000-023",
        "000-034",
    )


def test_frozen_table_is_a_zero_diagonal_latin_square() -> None:
    size = len(SPOKEN)
    expected = set(range(size))
    assert len(DAMM_26_TABLE) == size
    assert all(len(row) == size for row in DAMM_26_TABLE)
    assert all(set(row) == expected for row in DAMM_26_TABLE)
    assert all(
        {DAMM_26_TABLE[row][column] for row in range(size)} == expected
        for column in range(size)
    )
    assert all(DAMM_26_TABLE[index][index] == 0 for index in range(size))


def test_frozen_table_is_weakly_totally_antisymmetric() -> None:
    size = len(SPOKEN)
    for state, first, second in itertools.product(range(size), repeat=3):
        left = DAMM_26_TABLE[DAMM_26_TABLE[state][first]][second]
        right = DAMM_26_TABLE[DAMM_26_TABLE[state][second]][first]
        assert left != right or first == second


def test_custom_table_is_copied_to_immutable_tuples() -> None:
    supplied = [list(row) for row in DAMM_26_TABLE]
    checker = Damm(SPOKEN, supplied)
    supplied[0][1] = 0
    assert checker.table == DAMM_26_TABLE
    assert isinstance(checker.table, tuple)
    assert all(isinstance(row, tuple) for row in checker.table)


def test_bundled_table_is_only_available_at_order_26() -> None:
    digits = Alphabet.derive(pool="0123456789", lookalikes={})
    with pytest.raises(InvalidScheme, match="custom table"):
        Damm(digits)


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda table: table.pop(), "26 rows"),
        (lambda table: table[0].pop(), "26 entries"),
        (lambda table: table[0].__setitem__(1, True), "integers"),
        (lambda table: table[0].__setitem__(1, "2"), "integers"),
        (lambda table: table[0].__setitem__(1, 26), "between 0 and 25"),
        (lambda table: table[0].__setitem__(1, table[0][2]), "row 0"),
        (
            lambda table: (
                table[0].__setitem__(1, table[0][2]),
                table[0].__setitem__(2, 2),
            ),
            "column",
        ),
        (
            lambda table: table.__setitem__(slice(1, 3), [table[2], table[1]]),
            "diagonal",
        ),
    ],
)
def test_custom_table_validation(
    change: Callable[[list[list[Any]]], object],
    message: str,
) -> None:
    table: list[list[Any]] = [list(row) for row in DAMM_26_TABLE]
    change(table)
    with pytest.raises(InvalidScheme, match=message):
        Damm(SPOKEN, table)


def test_custom_table_must_be_weakly_totally_antisymmetric() -> None:
    size = len(SPOKEN)
    subtraction = [
        [(right - left) % size for right in range(size)] for left in range(size)
    ]
    with pytest.raises(InvalidScheme, match="weakly totally anti-symmetric"):
        Damm(SPOKEN, subtraction)


def test_compute_refuses_a_character_it_does_not_know() -> None:
    with pytest.raises(InvalidArgument, match="not in the alphabet"):
        Damm(SPOKEN).compute("A")


@pytest.mark.parametrize("short", ["", "0", "4"])
def test_verify_rejects_something_too_short(short: str) -> None:
    assert not Damm(SPOKEN).verify(short)


@pytest.mark.parametrize(
    "junk",
    [None, b"00000012", 12345, ["0", "0"], 3.5, "0000001A", "0000-0012"],
)
def test_verify_answers_false_for_junk(junk: object) -> None:
    assert Damm(SPOKEN).verify(junk) is False


def test_catches_every_substitution_and_adjacent_unequal_swap() -> None:
    checker = Damm(SPOKEN)
    chars = SPOKEN.characters
    substitutions = swaps = 0

    for body_length in range(1, 4):
        for symbols in itertools.product(chars, repeat=body_length):
            body = "".join(symbols)
            original = body + checker.compute(body)

            for position, typed in enumerate(original):
                for replacement in chars:
                    if replacement == typed:
                        continue
                    substitutions += 1
                    candidate = (
                        original[:position] + replacement + original[position + 1 :]
                    )
                    assert not checker.verify(candidate)

            for position in range(len(original) - 1):
                if original[position] == original[position + 1]:
                    continue
                swaps += 1
                candidate = (
                    original[:position]
                    + original[position + 1]
                    + original[position]
                    + original[position + 2 :]
                )
                assert not checker.verify(candidate)

    assert substitutions > 1_800_000
    assert swaps > 50_000
