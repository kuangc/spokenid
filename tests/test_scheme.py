"""Issuing, reading and sizing identifiers."""

from __future__ import annotations

from fractions import Fraction

import pytest

from spokenid import (
    SPOKEN,
    Alphabet,
    Damm,
    InvalidArgument,
    InvalidScheme,
    Luhn,
    Scheme,
    SequenceExhausted,
    SpaceExhausted,
    SpokenIdError,
    Unreadable,
)
from spokenid.scheme import MAX_LENGTH


@pytest.fixture
def scheme() -> Scheme:
    return Scheme()


# ------------------------------------------------------------------ shape


def test_default_shape(scheme: Scheme) -> None:
    assert scheme.length == 8
    assert scheme.body_length == 7
    assert scheme.space == 26**7
    assert len(scheme.random()) == 9  # eight characters and one separator


def test_default_checker_is_damm(scheme: Scheme) -> None:
    assert isinstance(scheme._checker, Damm)


def test_default_sequence_uses_the_frozen_damm_table(scheme: Scheme) -> None:
    assert scheme.next("0000-0000") == "0000-0012"


def test_other_even_alphabets_keep_the_luhn_fallback() -> None:
    digits = Alphabet.derive(drop_vowels=False, lookalikes={}, pool="0123456789")
    assert isinstance(Scheme(alphabet=digits)._checker, Luhn)


def test_an_explicit_luhn_checker_is_preserved() -> None:
    checker = Luhn(SPOKEN)
    assert Scheme(check=checker)._checker is checker


def test_an_explicit_damm_checker_is_preserved() -> None:
    checker = Damm(SPOKEN)
    assert Scheme(check=checker)._checker is checker


def test_an_explicit_checker_must_use_the_scheme_alphabet() -> None:
    digits = Alphabet.derive(drop_vowels=False, lookalikes={}, pool="0123456789")
    with pytest.raises(InvalidScheme, match="same alphabet"):
        Scheme(check=Luhn(digits))


def test_groups_must_add_up() -> None:
    with pytest.raises(InvalidScheme, match="add up to"):
        Scheme(length=8, groups=(3, 3))


def test_empty_group_is_refused() -> None:
    with pytest.raises(InvalidScheme, match="at least one character"):
        Scheme(length=8, groups=(8, 0))


def test_negative_group_is_refused() -> None:
    with pytest.raises(InvalidScheme, match="at least one"):
        Scheme(length=8, groups=(9, -1))


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
    with pytest.raises(SpaceExhausted, match="3 collisions in a row"):
        scheme.random(taken=lambda _: True, attempts=3)


def test_random_retry_exhaustion_does_not_claim_the_space_is_full(
    scheme: Scheme, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Even a single reserved ID can be drawn repeatedly in a mostly empty space.
    monkeypatch.setattr("spokenid.scheme.secrets.choice", lambda chars: chars[0])
    reserved = {scheme.first()}
    with pytest.raises(SpaceExhausted) as caught:
        scheme.random(taken=reserved.__contains__, attempts=3)
    message = str(caught.value)
    assert "3 collisions in a row" in message
    assert "does not prove the space is full" in message
    assert "outgrown" not in message


@pytest.mark.parametrize("attempts", [True, 1.5, "3", None])
def test_random_attempts_must_be_a_whole_number(scheme: Scheme, attempts: object) -> None:
    with pytest.raises(InvalidArgument, match="whole number"):
        scheme.random(attempts=attempts)  # type: ignore[arg-type]


@pytest.mark.parametrize("attempts", [0, -1])
def test_random_attempts_must_be_positive(scheme: Scheme, attempts: int) -> None:
    with pytest.raises(InvalidArgument, match="at least 1"):
        scheme.random(attempts=attempts)


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


def test_counted_gaps_are_not_presented_as_hiding_issue_order() -> None:
    documentation = Scheme.next.__doc__ or ""

    assert "random.randint" not in documentation
    assert "enumerable" in documentation
    assert "random()" in documentation
    assert "predictability" in documentation


@pytest.mark.parametrize("step", [True, 1.5, "3", None])
def test_next_step_must_be_a_whole_number(scheme: Scheme, step: object) -> None:
    with pytest.raises(InvalidArgument, match="whole number"):
        scheme.next(scheme.first(), step=step)  # type: ignore[arg-type]


@pytest.mark.parametrize("step", [0, -1])
def test_next_step_must_be_positive(scheme: Scheme, step: int) -> None:
    with pytest.raises(InvalidArgument, match="at least 1"):
        scheme.next(scheme.first(), step=step)


def test_next_reads_a_messy_previous(scheme: Scheme) -> None:
    tidy = scheme.next(scheme.first())
    messy = tidy.lower().replace("-", " ")
    assert scheme.next(messy) == scheme.next(tidy)


def test_next_refuses_a_previous_identifier_that_needed_repairs() -> None:
    with pytest.raises(Unreadable, match="confirm"):
        Scheme().next("OOOO-OOOO")


def test_end_of_the_sequence() -> None:
    tiny = Scheme(length=2, groups=(2,), separator="")
    last = tiny._finish(SPOKEN.characters[-1])
    with pytest.raises(SequenceExhausted, match="last identifier"):
        tiny.next(last)


def test_next_errors_do_not_echo_unbounded_previous_input() -> None:
    scheme = Scheme()
    last = scheme._finish(SPOKEN.characters[-1] * scheme.body_length)
    cases = (
        (10**5000, Unreadable),
        (" " * 100_000 + "OOOO-OOOO", Unreadable),
        (" " * 100_000 + last, SequenceExhausted),
    )

    for previous, error in cases:
        with pytest.raises(error) as caught:
            scheme.next(previous)  # type: ignore[arg-type]
        assert len(str(caught.value)) < 500


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


@pytest.mark.parametrize(
    ("raw", "scheme", "column"),
    [
        ("0000o000", Scheme(), 5),
        ("0000---o000", Scheme(), 8),
        (" 0000 o000", Scheme(), 7),
        ("0000::::o000", Scheme(length=8, separator="::"), 9),
    ],
)
def test_repairs_preserve_the_raw_character_and_column(
    raw: str, scheme: Scheme, column: int
) -> None:
    read = scheme.parse(raw)
    assert read.ok
    assert read.repairs[0].typed == "o"
    assert read.repairs[0].column == column


def test_failed_checksum_keeps_repairs_for_the_caller() -> None:
    read = Scheme().parse("o000-0002")
    assert not read.ok
    assert read.repairs[0].typed == "o"


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


@pytest.mark.parametrize("raw", ["0000-0000", "OOOO-OOOO", "OOOO-OOO1", "nope"])
def test_parsed_requires_an_explicit_boolean_decision(scheme: Scheme, raw: str) -> None:
    with pytest.raises(TypeError, match=r"\.status.*\.exact"):
        bool(scheme.parse(raw))


@pytest.mark.parametrize(
    ("raw", "status", "exact", "requires_confirmation"),
    [
        ("7HW2-0J43", "exact", True, False),
        (" 7hw2 0j43 ", "exact", True, False),
        ("7hw2 oj43", "confirmation_required", False, True),
        ("OOOO-OOO1", "invalid", False, False),
        ("0000-001W", "invalid", False, False),
        ("nope", "invalid", False, False),
        (None, "invalid", False, False),
    ],
)
def test_parse_status_distinguishes_repairs_from_invalid_input(
    scheme: Scheme, raw: object, status: str, exact: bool, requires_confirmation: bool
) -> None:
    parsed = scheme.parse(raw)
    assert parsed.status == status
    assert parsed.exact is exact
    assert parsed.requires_confirmation is requires_confirmation
    assert parsed.ok is (exact or requires_confirmation)


def test_failed_checksum_with_repairs_is_not_a_confirmation_candidate() -> None:
    parsed = Scheme().parse("OOOO-OOO1")
    assert parsed.repairs
    assert parsed.value is None
    assert parsed.status == "invalid"
    assert not parsed.requires_confirmation


@pytest.mark.parametrize(
    ("raw", "canonical"),
    [
        ("7HW2-0J43", True),
        ("7hw2-0j43", False),
        ("7HW20J43", False),
        ("7HW2 0J43", False),
        (" 7HW2-0J43 ", False),
        ("7HW2--0J43", False),
        ("7hw2 oj43", False),
        ("0000-001W", False),
        ("", False),
        (None, False),
        (123, False),
        (b"7HW2-0J43", False),
    ],
)
def test_is_canonical_requires_valid_storage_text(
    scheme: Scheme, raw: object, canonical: bool
) -> None:
    assert scheme.is_canonical(raw) is canonical


@pytest.mark.parametrize("separator", ["", "-", "::", " ", "e"])
@pytest.mark.parametrize("check", [True, False])
def test_is_canonical_uses_the_configured_format(separator: str, check: bool) -> None:
    scheme = Scheme(length=5, groups=(2, 3), separator=separator, check=check)
    for issued in (scheme.first(), scheme.next(scheme.first()), scheme.random()):
        assert scheme.is_canonical(issued)
        assert scheme.validate(f" {issued} ")
        assert not scheme.is_canonical(f" {issued} ")


def test_is_canonical_supports_a_custom_alphabet_and_checker() -> None:
    digits = Alphabet.derive(drop_vowels=False, lookalikes={}, pool="0123456789")
    scheme = Scheme(alphabet=digits, length=4, groups=(1, 3), separator="::")
    assert scheme.is_canonical(scheme.next(scheme.first()))
    assert not scheme.is_canonical("0::001")  # correct format, wrong Luhn check


def test_validate_is_strict_about_repairs(scheme: Scheme) -> None:
    assert scheme.validate("0000-0000")
    # Readable, but only after a repair, so it is not already correct.
    assert scheme.parse("OOOO-OOOO").ok
    assert not scheme.validate("OOOO-OOOO")


# ------------------------------------------------------------------ sizing


def test_guess_odds(scheme: Scheme) -> None:
    assert scheme.guess_odds(0) == Fraction(0)
    assert scheme.guess_odds(scheme.space) == Fraction(1)
    assert scheme.guess_odds(scheme.space * 2) == Fraction(1)
    assert 0 < scheme.guess_odds(100_000) < 1


def test_guess_odds_stays_nonzero_for_the_largest_scheme() -> None:
    biggest = Scheme(length=MAX_LENGTH)
    odds = biggest.guess_odds(1)
    assert isinstance(odds, Fraction)
    assert odds == Fraction(1, biggest.space)
    assert odds > 0


@pytest.mark.parametrize("members", [True, 1.5, "3", None])
def test_guess_odds_members_must_be_a_whole_number(
    scheme: Scheme, members: object
) -> None:
    with pytest.raises(InvalidArgument, match="whole number"):
        scheme.guess_odds(members)  # type: ignore[arg-type]


def test_guess_odds_refuses_negative_members(scheme: Scheme) -> None:
    with pytest.raises(InvalidArgument, match="negative"):
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


def test_random_exhaustion_guidance_preserves_the_scheme_semantics() -> None:
    digits = Alphabet.derive(drop_vowels=False, lookalikes={}, pool="0123456789")
    custom = Scheme(alphabet=digits, length=2, groups=(2,), separator="", check=False)
    with pytest.raises(SpaceExhausted) as caught:
        custom.random(taken=lambda _: True, attempts=1)
    message = str(caught.value)
    assert "same alphabet and checker" in message
    assert "Scheme(length=" not in message


def test_sequence_exhaustion_guidance_preserves_the_scheme_semantics() -> None:
    digits = Alphabet.derive(drop_vowels=False, lookalikes={}, pool="0123456789")
    custom = Scheme(alphabet=digits, length=2, groups=(2,), separator="", check=False)
    with pytest.raises(SequenceExhausted) as caught:
        custom.next("99")
    message = str(caught.value)
    assert "same alphabet and checker" in message
    assert "Scheme(length=" not in message


def test_random_exhaustion_at_maximum_length_gives_a_possible_alternative() -> None:
    biggest = Scheme(length=MAX_LENGTH)
    with pytest.raises(SpaceExhausted) as caught:
        biggest.random(taken=lambda _: True, attempts=1)
    message = str(caught.value)
    assert "maximum supported length" in message
    assert "longer scheme" not in message


def test_sequence_exhaustion_at_maximum_length_gives_a_possible_alternative() -> None:
    biggest = Scheme(length=MAX_LENGTH)
    last = biggest._finish(SPOKEN.characters[-1] * biggest.body_length)
    with pytest.raises(SequenceExhausted) as caught:
        biggest.next(last)
    message = str(caught.value)
    assert "maximum supported length" in message
    assert "longer scheme" not in message


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
    assert len(scheme._flatten("0000-0ßDD").normalized) == scheme.length
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


def test_repair_column_counts_the_way_a_person_reads() -> None:
    """Position indexes the string; column is what somebody counts on a form."""
    wide = Scheme(length=10)
    read = wide.parse("WP2-47R-P74O")
    assert [(r.position, r.column) for r in read.repairs] == [(9, 12)]
    assert "character 12" in str(read.repairs[0])


def test_describe_refuses_a_negative_population(scheme: Scheme) -> None:
    with pytest.raises(InvalidArgument, match="negative"):
        scheme.describe([-5])


def test_describe_accepts_a_zero_population(scheme: Scheme) -> None:
    assert "never" in scheme.describe([0])


@pytest.mark.parametrize("members", [True, 1.5, "3", None])
def test_describe_populations_must_be_whole_numbers(
    scheme: Scheme, members: object
) -> None:
    with pytest.raises(InvalidArgument, match="whole number"):
        scheme.describe([members])  # type: ignore[list-item]


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


def test_a_separator_that_grows_when_upper_cased_is_refused() -> None:
    """U+1E9A upper-cases into two characters, so reading could not strip it.

    ß and ﬁ do not test this guard: they are caught by the later clash check,
    because they upper-case into S and F. This one clashes with nothing, so
    without the guard the scheme is accepted and then cannot read its own
    output.
    """
    with pytest.raises(InvalidScheme, match="changes length when upper-cased"):
        Scheme(separator="\u1e9a")


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


def test_a_scheme_cannot_issue_more_than_the_parser_will_read() -> None:
    with pytest.raises(InvalidScheme, match="far too long to read back"):
        Scheme(
            length=MAX_LENGTH,
            groups=(1,) * MAX_LENGTH,
            separator="-" * 16,
        )


# --- sizes big enough to break str(int) -------------------------------------


def test_an_absurd_length_is_refused_rather_than_breaking_later() -> None:
    """str() refuses an integer over 4300 digits, which broke describe()."""
    with pytest.raises(InvalidScheme, match="supported maximum"):
        Scheme(length=MAX_LENGTH + 1)
    biggest = Scheme(length=MAX_LENGTH)
    assert biggest.describe([1])
    assert biggest.validate(biggest.random())


def test_attacker_sized_integer_errors_never_format_the_integer() -> None:
    """Valid integers beyond Python's decimal limit still raise library errors."""
    huge = 10**5000
    scheme = Scheme()

    calls = (
        lambda: Scheme(length=huge),
        lambda: Scheme(groups=(huge,)),
        lambda: scheme.next(scheme.first(), step=huge),
    )
    for call in calls:
        with pytest.raises(SpokenIdError) as caught:
            call()
        # Formatting the exception itself must remain safe too.
        assert str(caught.value)


def test_describe_bounds_an_attacker_sized_population() -> None:
    report = Scheme().describe([10**5000])

    assert "or more members" in report
    assert "always" in report
    assert "uniform full-space guess" in report
    assert "no allocation knowledge" in report


def test_guess_odds_states_its_uniform_no_knowledge_model() -> None:
    documentation = Scheme.guess_odds.__doc__ or ""

    assert "uniform full-space guess" in documentation
    assert "no knowledge" in documentation


def test_describe_rounds_a_non_integral_reciprocal_instead_of_flooring() -> None:
    binary = Alphabet("01")
    scheme = Scheme(
        alphabet=binary,
        length=3,
        groups=(3,),
        separator="",
        check=False,
    )

    report = scheme.describe([2, 3])

    assert "1 in 4 exactly" in report
    assert "about 1 in 3" in report
    assert "about 1 in 2" not in report


def test_describe_keeps_near_capacity_risk_distinct_from_always() -> None:
    tiny = Scheme(length=2, groups=(2,), separator="")

    report = tiny.describe([20])

    assert "76.9% of the time" in report
    assert "about 1 in 1" not in report

    almost_full = Scheme()
    report = almost_full.describe([almost_full.space - 1])
    assert "more than 99.9% but not always" in report
    assert "names a real one 100.0%" not in report


def test_short_number_formatting_is_well_formed() -> None:
    from spokenid.scheme import _short

    assert _short(1) == "1.00e+0"
    assert _short(10) == "1.00e+1"
    assert _short(1234) == "1.23e+3"


@pytest.mark.parametrize("length", ["eight", 2.5, True, None, [8]])
def test_length_must_be_a_whole_number(length: object) -> None:
    """default_groups() divides by length, so a bad one used to raise late."""
    with pytest.raises(InvalidScheme, match="whole number"):
        Scheme(length=length)  # type: ignore[arg-type]


@pytest.mark.parametrize("length", [True, 2.5, "8", None])
def test_default_groups_length_must_be_a_whole_number(length: object) -> None:
    from spokenid import default_groups

    with pytest.raises(InvalidArgument, match="whole number"):
        default_groups(length)  # type: ignore[arg-type]


@pytest.mark.parametrize("length", [0, -1])
def test_default_groups_length_must_be_positive(length: int) -> None:
    from spokenid import default_groups

    with pytest.raises(InvalidArgument, match="at least 1"):
        default_groups(length)


@pytest.mark.parametrize("length", [MAX_LENGTH + 1, 10**400])
def test_default_groups_rejects_lengths_the_library_cannot_support(length: int) -> None:
    from spokenid import default_groups

    with pytest.raises(InvalidArgument, match=f"at most {MAX_LENGTH}"):
        default_groups(length)


@pytest.mark.parametrize("length", [10**400, 500_000_000, 10**18])
def test_an_enormous_length_is_refused_immediately(length: int) -> None:
    """It used to raise OverflowError, or allocate gigabytes, before the guard."""
    import time

    started = time.perf_counter()
    with pytest.raises(InvalidScheme, match="supported maximum"):
        Scheme(length=length)
    assert time.perf_counter() - started < 0.5


def test_suggest_ignores_input_too_long_to_read(scheme: Scheme) -> None:
    from spokenid.scheme import MAX_MEANINGFUL

    assert scheme.suggest("0" * (MAX_MEANINGFUL + 10)) == ()


@pytest.mark.parametrize("groups", [(4.0, 4.0), (4, "4"), (True, 7), (4, None)])
def test_group_sizes_must_be_whole_numbers(groups: object) -> None:
    """sum() used to raise TypeError before any friendly message."""
    with pytest.raises(InvalidScheme, match="whole number"):
        Scheme(length=8, groups=groups)  # type: ignore[arg-type]


@pytest.mark.parametrize("check", [None, "no", 1, 0, "", object()])
def test_check_must_be_boolean_or_a_checker(check: object) -> None:
    """A truthy value used to quietly give you a scheme with no check digit."""
    with pytest.raises(InvalidScheme, match="boolean or a Damm or Luhn checker"):
        Scheme(check=check)  # type: ignore[arg-type]


def test_random_without_a_uniqueness_check_can_repeat() -> None:
    """The README used to say it retries. It only retries when asked."""
    small = Scheme(length=3, groups=(3,), separator="")
    drawn = [small.random() for _ in range(200)]
    assert len(set(drawn)) < len(drawn), "expected repeats from a 676-wide space"
    unique = []
    seen: set[str] = set()
    for _ in range(200):
        got = small.random(taken=seen.__contains__)
        seen.add(got)
        unique.append(got)
    assert len(set(unique)) == len(unique)
