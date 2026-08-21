"""Near-miss recovery: what to offer when parse() says no."""

from __future__ import annotations

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from spokenid import SPOKEN, InvalidArgument, Scheme

BODY = st.text(alphabet=SPOKEN.characters, min_size=7, max_size=7)


@pytest.fixture
def scheme() -> Scheme:
    return Scheme()


def test_a_wrong_character_is_always_recoverable(scheme: Scheme) -> None:
    real = scheme.random()
    flat = real.replace("-", "")
    for position in range(len(flat)):
        wrong = SPOKEN.characters[(SPOKEN.characters.index(flat[position]) + 1) % 26]
        typo = flat[:position] + wrong + flat[position + 1 :]
        assert not scheme.parse(typo).ok
        assert real in scheme.suggest(typo), (position, typo)


def test_a_dropped_character_is_recoverable(scheme: Scheme) -> None:
    real = scheme.random()
    flat = real.replace("-", "")
    for position in range(len(flat)):
        assert real in scheme.suggest(flat[:position] + flat[position + 1 :])


def test_a_doubled_character_is_recoverable(scheme: Scheme) -> None:
    real = scheme.random()
    flat = real.replace("-", "")
    for position in range(len(flat)):
        assert real in scheme.suggest(flat[: position + 1] + flat[position:])


def test_a_swap_is_recoverable(scheme: Scheme) -> None:
    real = scheme.random()
    flat = real.replace("-", "")
    swaps = [i for i in range(len(flat) - 1) if flat[i] != flat[i + 1]]
    assert swaps, "a random identifier of eight characters has adjacent differences"
    for position in swaps:
        typo = (
            flat[:position] + flat[position + 1] + flat[position] + flat[position + 2 :]
        )
        assert real in scheme.suggest(typo)


def test_every_suggestion_is_actually_valid(scheme: Scheme) -> None:
    for candidate in scheme.suggest("0000-001W"):
        assert scheme.validate(candidate)


def test_a_lookalike_substitution_is_offered_first(scheme: Scheme) -> None:
    """0 and Q stay confusable inside the alphabet, so rank that ahead."""
    assert frozenset("0Q") in SPOKEN.similar
    real = "0000-0000"
    assert scheme.validate(real)
    assert scheme.suggest("000Q-0000")[0] == real


def test_the_answer_is_never_the_input(scheme: Scheme) -> None:
    real = scheme.random()
    assert real not in scheme.suggest(real)


def test_there_is_no_such_thing_as_a_near_miss_without_a_check_character() -> None:
    unchecked = Scheme(check=False)
    assert unchecked.suggest(unchecked.random()) == ()


@pytest.mark.parametrize("junk", [None, 12345, b"x", ["x"], "", "!!!", "x" * 9000])
def test_suggest_answers_anything(scheme: Scheme, junk: object) -> None:
    assert isinstance(scheme.suggest(junk), tuple)


def test_limit_is_honoured_and_validated(scheme: Scheme) -> None:
    assert len(scheme.suggest("0000-001W", limit=3)) == 3
    with pytest.raises(InvalidArgument, match="at least 1"):
        scheme.suggest("0000-001W", limit=0)


@given(BODY)
def test_one_wrong_character_always_yields_the_original(body: str) -> None:
    """The property the whole feature rests on."""
    scheme = Scheme()
    real = scheme._finish(body)
    flat = real.replace("-", "")
    wrong = SPOKEN.characters[(SPOKEN.characters.index(flat[0]) + 7) % 26]
    assume(wrong != flat[0])
    assert real in scheme.suggest(wrong + flat[1:])
