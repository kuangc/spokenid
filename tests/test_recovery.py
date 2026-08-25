"""Exact recovery properties independent of synthetic cohort measurements."""

from __future__ import annotations

import pytest
from benchmarks.evaluate import classify_parse, error_events

from spokenid import Scheme


@pytest.mark.parametrize(
    "kind",
    ["substitution", "adjacent_transposition", "insertion", "deletion"],
)
def test_the_source_is_suggested_for_every_documented_one_edit(kind: str) -> None:
    scheme = Scheme()
    source = scheme.next(scheme.first(), step=12_345)

    for typed in error_events(scheme, source, kind):
        assert source in scheme.suggest(typed), (kind, source, typed)


def test_a_valid_unissued_identifier_is_not_classified_as_a_wrong_record() -> None:
    scheme = Scheme()
    source = scheme.first()
    unissued = scheme.next(source)

    assert classify_parse(scheme.parse(unissued), source, {source}) == (
        "accepted_unissued"
    )
