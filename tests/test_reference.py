"""The fast reading path has to agree with an obviously-correct slow one.

`_flatten` has been the source of three separate regressions: counting
separators before removing them, upper-casing before stripping, and an early
exit that discarded trailing text. Each was a clever optimisation that changed
behaviour by accident.

So here is the same job written the dull way, with no bounds and no early exit,
and a property test that the real one always agrees with it. Any future
optimisation that changes what is accepted fails here.
"""

from __future__ import annotations

import string

from hypothesis import HealthCheck, assume, given, settings
from hypothesis import strategies as st

from spokenid import SPOKEN, Scheme


def reference_flatten(scheme: Scheme, raw: str) -> str:
    """Drop whitespace, upper-case, drop separators. Nothing else."""
    without_space = "".join(c for c in raw if not c.isspace())
    upper = "".join(c.upper() if len(c.upper()) == 1 else c for c in without_space)
    separator = scheme.separator.upper()
    return upper.replace(separator, "") if separator else upper


def reference_parse(scheme: Scheme, raw: str) -> str | None:
    """The canonical identifier, or None. Deliberately slow and obvious."""
    flat = reference_flatten(scheme, raw)
    if len(flat) != scheme.length:
        return None
    out = []
    for char in flat:
        if char in scheme.alphabet.characters:
            out.append(char)
        elif char in scheme.alphabet.repairs:
            out.append(scheme.alphabet.repairs[char])
        else:
            return None
    fixed = "".join(out)
    if scheme.check:
        from spokenid import Luhn

        if not Luhn(scheme.alphabet).verify(fixed):
            return None
    pieces, start = [], 0
    for size in scheme.groups:
        pieces.append(fixed[start : start + size])
        start += size
    return scheme.separator.join(pieces)


# Text made mostly of things that matter: alphabet characters, repairs,
# separators and whitespace, so the interesting cases actually come up.
INTERESTING = st.text(
    alphabet=st.sampled_from(
        SPOKEN.characters + "".join(SPOKEN.repairs) + "-  \t\n" + "aeiouß!"
    ),
    max_size=40,
)


@given(INTERESTING)
@settings(max_examples=500, suppress_health_check=[HealthCheck.too_slow])
def test_reading_agrees_with_the_obvious_implementation(raw: str) -> None:
    scheme = Scheme()
    assert scheme.parse(raw).value == reference_parse(scheme, raw)


@given(INTERESTING, st.integers(min_value=2, max_value=12))
@settings(max_examples=300, suppress_health_check=[HealthCheck.too_slow])
def test_agreement_holds_at_every_length(raw: str, length: int) -> None:
    scheme = Scheme(length=length)
    assert scheme.parse(raw).value == reference_parse(scheme, raw)


@given(INTERESTING, st.sampled_from(["-", "", ".", "::", " ", "/"]))
@settings(max_examples=300, suppress_health_check=[HealthCheck.too_slow])
def test_agreement_holds_for_every_separator(raw: str, separator: str) -> None:
    scheme = Scheme(separator=separator)
    assert scheme.parse(raw).value == reference_parse(scheme, raw)


@given(st.text(alphabet=string.printable, max_size=60))
@settings(max_examples=400, suppress_health_check=[HealthCheck.too_slow])
def test_agreement_holds_for_arbitrary_printable_text(raw: str) -> None:
    scheme = Scheme()
    assert scheme.parse(raw).value == reference_parse(scheme, raw)


TRAILING = st.text(
    alphabet=st.sampled_from(SPOKEN.characters + "-  " + "aeiou"), max_size=20
)


@given(st.integers(min_value=0, max_value=30), TRAILING)
@settings(max_examples=400, suppress_health_check=[HealthCheck.too_slow])
def test_a_valid_identifier_with_anything_appended_is_refused(
    padding: int, trailing: str
) -> None:
    """The failure that shipped: input truncated into a valid identifier.

    `parse("0000-001X --- Jane Doe")` returned the identifier and dropped the
    name. Anything after a complete identifier has to make it invalid.
    """
    scheme = Scheme()
    identifier = scheme.random()
    meaningful = [c for c in trailing if not c.isspace() and c != scheme.separator]
    assume(meaningful)  # otherwise the tail is only padding, which is allowed
    attacked = identifier + scheme.separator * padding + trailing
    read = scheme.parse(attacked)
    assert not read.ok, f"{attacked!r} was accepted as {read.value!r}"


@given(st.integers(min_value=0, max_value=40))
@settings(max_examples=100)
def test_separator_padding_alone_is_still_forgiven(padding: int) -> None:
    scheme = Scheme()
    identifier = scheme.random()
    padded = scheme.separator * padding + identifier + scheme.separator * padding
    assert scheme.parse(padded).value == identifier
