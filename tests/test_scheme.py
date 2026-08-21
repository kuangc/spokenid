"""Issuing, reading and sizing identifiers."""

from __future__ import annotations

import pytest

from spokenid import (
    SPOKEN,
    Alphabet,
    InvalidScheme,
    Scheme,
    SequenceExhausted,
    SpaceExhausted,
)


@pytest.fixture
def scheme() -> Scheme:
    return Scheme()


# ------------------------------------------------------------------ shape


def test_default_shape(scheme: Scheme) -> None:
    assert scheme.length == 8
    assert scheme.body_length == 7
    assert scheme.space == 26**7
    assert len(scheme.random()) == 9  # eight characters and one separator


def test_groups_must_add_up() -> None:
    with pytest.raises(InvalidScheme, match="add up to"):
        Scheme(length=8, groups=(3, 3))


def test_empty_group_is_refused() -> None:
    with pytest.raises(InvalidScheme, match="at least one character"):
        Scheme(length=8, groups=(8, 0))


def test_separator_cannot_be_a_character_in_the_alphabet() -> None:
    with pytest.raises(InvalidScheme, match="already means something by"):
        Scheme(length=8, groups=(4, 4), separator="7")


def test_too_short_is_refused() -> None:
    with pytest.raises(InvalidScheme, match="at least two"):
        Scheme(length=1, groups=(1,))


def test_odd_alphabet_needs_check_turned_off() -> None:
    odd = Alphabet.derive(lookalikes={"I": "1", "O": "0", "B": "8", "S": "5"})
    with pytest.raises(InvalidScheme, match="even number of characters"):
        Scheme(alphabet=odd)
    works = Scheme(alphabet=odd, check=False)
    assert works.validate(works.random())


def test_scheme_is_hashable(scheme: Scheme) -> None:
    assert len({scheme, Scheme()}) == 1


def test_groups_given_as_a_list_still_works() -> None:
    assert Scheme(length=8, groups=[4, 4]).random()


# ------------------------------------------------------------------ random


def test_random_is_valid(scheme: Scheme) -> None:
    for _ in range(200):
        assert scheme.validate(scheme.random())


def test_random_retries_past_a_taken_identifier(scheme: Scheme) -> None:
    seen: list[str] = []

    def taken(candidate: str) -> bool:
        # Refuse the first two candidates, accept the third.
        seen.append(candidate)
        return len(seen) < 3

    assert scheme.random(taken=taken) == seen[-1]
    assert len(seen) == 3


def test_random_gives_up_loudly(scheme: Scheme) -> None:
    with pytest.raises(SpaceExhausted, match="outgrown"):
        scheme.random(taken=lambda _: True, attempts=3)


def test_attempts_must_be_positive(scheme: Scheme) -> None:
    with pytest.raises(ValueError, match="at least 1"):
        scheme.random(attempts=0)


# ------------------------------------------------------------------ counting


def test_first_then_next(scheme: Scheme) -> None:
    first = scheme.first()
    assert scheme.validate(first)
    assert scheme.validate(scheme.next(first))
    assert scheme.next(first) != first


def test_counting_never_repeats_and_stays_in_order(scheme: Scheme) -> None:
    issued = [scheme.first()]
    for _ in range(5_000):
        issued.append(scheme.next(issued[-1]))
    assert len(set(issued)) == len(issued)
    assert sorted(issued) == issued  # sorts into the order they were issued


def test_step_leaves_gaps_but_keeps_order(scheme: Scheme) -> None:
    issued = [scheme.first()]
    for size in (1, 7, 50, 999):
        issued.append(scheme.next(issued[-1], step=size))
    assert sorted(issued) == issued
    assert len(set(issued)) == len(issued)


def test_step_must_be_positive(scheme: Scheme) -> None:
    with pytest.raises(ValueError, match="at least 1"):
        scheme.next(scheme.first(), step=0)


def test_next_reads_a_messy_previous(scheme: Scheme) -> None:
    tidy = scheme.next(scheme.first())
    messy = tidy.lower().replace("-", " ")
    assert scheme.next(messy) == scheme.next(tidy)


def test_next_refuses_something_unreadable(scheme: Scheme) -> None:
    with pytest.raises(ValueError, match="cannot read"):
        scheme.next("nonsense")


def test_end_of_the_sequence() -> None:
    tiny = Scheme(length=2, groups=(2,), separator="")
    last = tiny._finish(SPOKEN.characters[-1])
    with pytest.raises(SequenceExhausted, match="last identifier"):
        tiny.next(last)


# ------------------------------------------------------------------ reading


def test_reads_case_and_spacing(scheme: Scheme) -> None:
    tidy = scheme.random()
    messy_forms = (
        tidy.lower(),
        tidy.replace("-", " "),
        f"  {tidy}  ",
        tidy.replace("-", ""),
    )
    for messy in messy_forms:
        read = scheme.parse(messy)
        assert read.ok
        assert read.value == tidy
        assert read.exact


def test_repairs_a_lookalike_and_says_so() -> None:
    scheme = Scheme()
    tidy = "0000-0000"
    read = scheme.parse("OOOO-OOOO")
    assert read.ok
    assert read.value == tidy
    assert len(read.repairs) == 8
    assert not read.exact
    assert all(r.typed == "O" and r.read_as == "0" for r in read.repairs)


def test_repairs_report_their_position() -> None:
    scheme = Scheme()
    read = scheme.parse("O000-0000")
    assert [(r.position, r.typed, r.read_as) for r in read.repairs] == [(0, "O", "0")]
    assert "character 1" in str(read.repairs[0])


def test_rejects_a_wrong_check_character(scheme: Scheme) -> None:
    tidy = scheme.random()
    flat = tidy.replace("-", "")
    wrong = SPOKEN.characters[(SPOKEN.characters.index(flat[-1]) + 1) % 26]
    read = scheme.parse(flat[:-1] + wrong)
    assert not read.ok
    assert "typing mistake" in (read.problem or "")


def test_rejects_a_vowel(scheme: Scheme) -> None:
    read = scheme.parse("AAAA-AAAA")
    assert not read.ok
    assert "vowel" in (read.problem or "")


def test_rejects_the_wrong_length(scheme: Scheme) -> None:
    read = scheme.parse("4KM7")
    assert not read.ok
    assert "8 characters" in (read.problem or "")


@pytest.mark.parametrize("empty", [None, "", "   ", "-"])
def test_rejects_nothing(scheme: Scheme, empty: str | None) -> None:
    read = scheme.parse(empty)
    assert not read.ok
    assert read.problem


def test_parsed_is_falsey_when_it_failed(scheme: Scheme) -> None:
    assert not scheme.parse("nope")
    assert scheme.parse(scheme.random())


def test_validate_is_strict_about_repairs(scheme: Scheme) -> None:
    assert scheme.validate("0000-0000")
    # Readable, but only after a repair, so it is not already correct.
    assert scheme.parse("OOOO-OOOO").ok
    assert not scheme.validate("OOOO-OOOO")


# ------------------------------------------------------------------ sizing


def test_guess_odds(scheme: Scheme) -> None:
    assert scheme.guess_odds(0) == 0
    assert scheme.guess_odds(scheme.space) == 1.0
    assert scheme.guess_odds(scheme.space * 2) == 1.0
    assert 0 < scheme.guess_odds(100_000) < 1


def test_guess_odds_refuses_nonsense(scheme: Scheme) -> None:
    with pytest.raises(ValueError, match="negative"):
        scheme.guess_odds(-1)


def test_describe_mentions_the_shape(scheme: Scheme) -> None:
    report = scheme.describe()
    assert "XXXX-XXXX" in report
    assert "8,031,810,176" in report


# ------------------------------------------------------------------ no check


def test_scheme_without_a_check_character() -> None:
    scheme = Scheme(check=False)
    assert scheme.body_length == scheme.length == 8
    assert scheme.validate(scheme.random())
    # Any well-formed string is now acceptable, because nothing verifies it.
    assert scheme.validate("0000-0000")


# ------------------------------------------------------------------ regressions


@pytest.mark.parametrize("length", list(range(2, 21)))
def test_any_length_works_without_naming_groups(length: int) -> None:
    """Groups used to default to (4, 4), so every length but 8 raised."""
    scheme = Scheme(length=length)
    assert sum(scheme.groups) == length
    assert scheme.validate(scheme.random())


def test_default_groups_shape() -> None:
    from spokenid import default_groups

    assert default_groups(4) == (4,)
    assert default_groups(6) == (3, 3)
    assert default_groups(7) == (3, 4)
    assert default_groups(8) == (4, 4)
    assert default_groups(9) == (3, 3, 3)
    assert default_groups(10) == (3, 3, 4)
    assert default_groups(12) == (4, 4, 4)


def test_the_remedy_an_error_suggests_actually_works(scheme: Scheme) -> None:
    """Both exhaustion messages name a Scheme(...) call. It has to be valid."""
    import re

    with pytest.raises(SpaceExhausted) as caught:
        scheme.random(taken=lambda _: True, attempts=1)
    match = re.search(r"Scheme\(length=(\d+)\)", str(caught.value))
    assert match
    suggested = Scheme(length=int(match.group(1)))
    assert suggested.space > scheme.space


@pytest.mark.parametrize("junk", [12345678, b"7HW2-0J46", ["7HW2-0J46"], 3.14, object()])
def test_parse_answers_things_that_are_not_text(scheme: Scheme, junk: object) -> None:
    read = scheme.parse(junk)
    assert not read.ok
    assert read.problem
    assert "is text" in read.problem


def test_next_raises_the_library_error(scheme: Scheme) -> None:
    from spokenid import SpokenIdError, Unreadable

    with pytest.raises(Unreadable):
        scheme.next("nonsense")
    with pytest.raises(SpokenIdError):
        scheme.next("nonsense")
    with pytest.raises(ValueError, match="cannot read"):  # still a ValueError
        scheme.next("nonsense")


@pytest.mark.parametrize("separator", ["0C", "YX", "XY", "O", "S", "0"])
def test_a_separator_cannot_reuse_an_alphabet_or_repair_character(separator: str) -> None:
    """`sep in chars` was a substring test, so 'YX' passed where 'XY' failed."""
    with pytest.raises(InvalidScheme, match="already means something by"):
        Scheme(length=8, groups=(4, 4), separator=separator)


def test_every_identifier_a_scheme_issues_can_be_read_back(scheme: Scheme) -> None:
    """A bad separator used to give sequences that died after ten steps."""
    current = scheme.first()
    for _ in range(200):
        assert scheme.parse(current).ok, current
        current = scheme.next(current)


def test_sizing_survives_absurd_numbers(scheme: Scheme) -> None:
    assert scheme.guess_odds(10**400) == 1.0  # used to raise OverflowError
    huge = Scheme(length=230, groups=(230,))
    report = huge.describe([10_000])
    assert "never" not in report  # a finite space was reported as no risk at all
    assert "inf" not in report


def test_describe_is_honest_at_the_edges() -> None:
    tiny = Scheme(length=4)
    assert "never" in tiny.describe([0])
    assert "always" in tiny.describe([tiny.space * 2])


def test_a_long_paste_costs_no_more_than_a_short_one(scheme: Scheme) -> None:
    """Reading stops once the result is already too long to be an identifier."""
    import time

    started = time.perf_counter()
    read = scheme.parse("O" * 5_000_000)
    elapsed = time.perf_counter() - started
    assert not read.ok
    assert elapsed < 0.1, f"took {elapsed:.3f}s, so it scanned the whole paste"


def test_padding_does_not_make_a_valid_identifier_invalid(scheme: Scheme) -> None:
    """An earlier cap measured the raw length and rejected this."""
    identifier = scheme.random()
    assert scheme.parse(" " * 100_000 + identifier).value == identifier


def test_a_character_that_upper_cases_to_two_is_one_mistake_not_two(
    scheme: Scheme,
) -> None:
    """'ß'.upper() == 'SS', which used to report two repairs at wrong positions."""
    # Eight characters once the separator goes, so length is not the complaint.
    assert len(scheme._flatten("0000-0ßDD")) == scheme.length
    read = scheme.parse("0000-0ßDD")
    assert not read.ok
    assert "ß" in (read.problem or "")
    # And one typed character never becomes two repairs.
    assert not read.repairs


@pytest.mark.parametrize(
    "call",
    [
        lambda s: s.random(attempts=0),
        lambda s: s.next(s.first(), step=0),
        lambda s: s.guess_odds(-1),
    ],
)
def test_argument_errors_are_library_errors(scheme: Scheme, call: object) -> None:
    from spokenid import InvalidArgument, SpokenIdError

    with pytest.raises(SpokenIdError):
        call(scheme)  # type: ignore[operator]
    with pytest.raises(InvalidArgument):
        call(scheme)  # type: ignore[operator]


def test_repair_column_counts_the_way_a_person_reads(scheme: Scheme) -> None:
    """Position indexes the string; column is what somebody counts on a form."""
    wide = Scheme(length=10)
    read = wide.parse("WP2-47R-P7KO")
    assert [(r.position, r.column) for r in read.repairs] == [(9, 12)]
    assert "character 12" in str(read.repairs[0])


def test_describe_refuses_a_negative_population(scheme: Scheme) -> None:
    from spokenid import InvalidArgument

    with pytest.raises(InvalidArgument, match="negative"):
        scheme.describe([-5])


# --- separators: the check and the reading have to agree about case ---------


def test_no_accepted_separator_produces_an_unreadable_identifier() -> None:
    """The clash check was case-sensitive while reading upper-cased.

    Eighteen lower-case separators passed the check and then deleted a body
    character, so a counted sequence died within a few steps.
    """
    import string

    for separator in string.printable + "ßﬁ":
        try:
            scheme = Scheme(separator=separator)
        except InvalidScheme:
            continue
        current = scheme.first()
        for step in range(40):
            assert scheme.parse(current).ok, (
                f"separator {separator!r} issued {current!r}, which it cannot read "
                f"back, after {step} steps"
            )
            current = scheme.next(current)


@pytest.mark.parametrize("separator", ["x", "c", "o", "s", "ß", "ﬁ"])
def test_a_separator_that_folds_into_the_alphabet_is_refused(separator: str) -> None:
    with pytest.raises(InvalidScheme):
        Scheme(separator=separator)


def test_a_separator_cannot_mix_whitespace_with_anything_else() -> None:
    """Reading strips whitespace first, so " - " could never match."""
    with pytest.raises(InvalidScheme, match="mixes whitespace"):
        Scheme(separator=" - ")


def test_a_separator_of_pure_whitespace_works() -> None:
    scheme = Scheme(length=9, groups=(3, 3, 3), separator=" ")
    identifier = scheme.first()
    assert " " in identifier
    assert scheme.parse(identifier).ok


def test_a_long_separator_can_still_be_read_back() -> None:
    scheme = Scheme(length=20, separator="-" * 30)
    assert scheme.parse(scheme.first()).ok


# --- sizes big enough to break str(int) -------------------------------------


def test_an_absurd_length_is_refused_rather_than_breaking_later() -> None:
    """str() refuses an integer over 4300 digits, which broke describe()."""
    from spokenid.scheme import MAX_LENGTH

    with pytest.raises(InvalidScheme, match="past the"):
        Scheme(length=MAX_LENGTH + 1)
    biggest = Scheme(length=MAX_LENGTH)
    assert biggest.describe([1])
    assert biggest.validate(biggest.random())


def test_short_number_formatting_is_well_formed() -> None:
    from spokenid.scheme import _short

    assert _short(1) == "1.00e+0"
    assert _short(10) == "1.00e+1"
    assert _short(1234) == "1.23e+3"
