"""Properties that must hold for every identifier, not just the ones we picked.

These are the library's promises. Each one is stated as something Hypothesis
tries to break, rather than as a sentence in the README.
"""

from __future__ import annotations

import string

from hypothesis import assume, given, settings
from hypothesis import strategies as st

from spokenid import SPOKEN, Scheme, phonetic


def scheme_of(length: int, check: bool = True) -> Scheme:
    return Scheme(length=length, groups=(length,), separator="-", check=check)


lengths = st.integers(min_value=2, max_value=14)


def bodies(scheme: Scheme) -> st.SearchStrategy[str]:
    """Identifier bodies drawn by Hypothesis, so a failure can be replayed.

    Using ``scheme.random()`` inside a property test makes it unreplayable,
    because the value comes from ``secrets`` rather than from the test engine.
    """
    return st.text(
        alphabet=SPOKEN.characters,
        min_size=scheme.body_length,
        max_size=scheme.body_length,
    )


@given(lengths)
def test_an_identifier_never_contains_a_vowel(length: int) -> None:
    identifier = scheme_of(length).random()
    assert not set(identifier) & set("AEIOU")


@given(lengths)
def test_an_identifier_only_uses_the_alphabet(length: int) -> None:
    scheme = scheme_of(length)
    flat = scheme.random().replace("-", "")
    assert set(flat) <= set(SPOKEN.characters)


@given(lengths)
def test_a_fresh_identifier_reads_back_exactly(length: int) -> None:
    scheme = scheme_of(length)
    identifier = scheme.random()
    read = scheme.parse(identifier)
    assert read.exact
    assert read.value == identifier


@given(lengths, st.integers(min_value=1, max_value=10_000))
def test_counting_moves_forward(length: int, step: int) -> None:
    scheme = scheme_of(length)
    assume(step < scheme.space - 1)
    first = scheme.first()
    following = scheme.next(first, step=step)
    assert following != first
    assert following > first  # ascending alphabet, so text order is issue order


@given(lengths)
def test_reading_is_idempotent(length: int) -> None:
    scheme = scheme_of(length)
    once = scheme.parse(scheme.random())
    assert once.value is not None
    twice = scheme.parse(once.value)
    assert twice.value == once.value
    assert twice.exact


@given(lengths, st.data())
def test_a_lookalike_always_repairs_to_the_original(
    length: int, data: st.DataObject
) -> None:
    """Type any confusable character and you get back what was meant."""
    scheme = scheme_of(length)
    identifier = scheme._finish(data.draw(bodies(scheme)))
    flat = identifier.replace("-", "")
    backwards = {v: k for k, v in SPOKEN.repairs.items()}
    positions = [i for i, c in enumerate(flat) if c in backwards]
    assume(positions)
    position = data.draw(st.sampled_from(positions))
    typo = flat[:position] + backwards[flat[position]] + flat[position + 1 :]
    read = scheme.parse(typo)
    assert read.ok
    assert read.value == identifier
    assert read.repairs


@given(lengths)
def test_case_and_spacing_never_matter(length: int) -> None:
    scheme = scheme_of(length)
    identifier = scheme.random()
    for messy in (
        identifier.lower(),
        identifier.replace("-", " "),
        identifier.replace("-", ""),
        f"\t {identifier}\n",
    ):
        assert scheme.parse(messy).value == identifier


@given(lengths, st.data())
@settings(max_examples=50)
def test_one_wrong_character_is_always_caught(length: int, data: st.DataObject) -> None:
    """The whole point of the check character."""
    scheme = scheme_of(length)
    identifier = scheme._finish(data.draw(bodies(scheme)))
    flat = identifier.replace("-", "")
    position = data.draw(st.integers(min_value=0, max_value=len(flat) - 1))
    replacement = data.draw(st.sampled_from(SPOKEN.characters))
    assume(replacement != flat[position])
    broken = flat[:position] + replacement + flat[position + 1 :]
    assert not scheme.parse(broken).ok


@given(st.text(alphabet=string.printable, max_size=30))
def test_reading_junk_never_raises(raw: str) -> None:
    """Anything a person can type gets an answer, never a traceback."""
    read = Scheme().parse(raw)
    assert isinstance(read.ok, bool)
    if read.ok:
        assert read.value is not None
    else:
        assert read.problem


@given(lengths)
def test_counting_and_reading_agree(length: int) -> None:
    scheme = scheme_of(length)
    current = scheme.first()
    for _ in range(20):
        assert scheme.validate(current)
        current = scheme.next(current)


@given(lengths)
def test_phonetic_covers_every_character(length: int) -> None:
    spoken = phonetic(scheme_of(length).random())
    assert spoken
    assert "None" not in spoken
