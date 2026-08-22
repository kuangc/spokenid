"""How often a mistyped identifier resolves to exactly one record.

The README publishes these rates in a table, and they differ sharply between
issuing by counting and issuing at random. Four rounds of review missed that,
because it only shows up when you do the whole job rather than call a method.
"""

from __future__ import annotations

import random
from collections.abc import Callable

import pytest

from spokenid import Scheme

TRIALS = 1500
MEMBERS = 1000


Issuer = Callable[[Scheme, str | None], str]


def _measure(issue: Issuer, members: int, trials: int) -> tuple[float, float]:
    """Returns (fraction with exactly one candidate, fraction where it is present)."""
    scheme = Scheme()
    records: set[str] = set()
    current = None
    for _ in range(members):
        current = issue(scheme, current)
        records.add(current)

    held = sorted(records)
    exactly_one = present = considered = 0
    picker = random.Random(20260821)  # noqa: S311 - measurement, not secrets
    for _ in range(trials):
        real = picker.choice(held)
        flat = real.replace("-", "")
        position = picker.randrange(len(flat))
        wrong = picker.choice(
            [c for c in scheme.alphabet.characters if c != flat[position]]
        )
        typed = flat[:position] + wrong + flat[position + 1 :]
        if scheme.parse(typed).ok:
            continue  # not every substitution is caught; those are a different case
        considered += 1
        candidates = [c for c in scheme.suggest(typed) if c in records]
        exactly_one += len(candidates) == 1
        present += real in candidates
    return exactly_one / considered, present / considered


def _counted(scheme: Scheme, current: str | None) -> str:
    return scheme.first() if current is None else scheme.next(current)


def _gapped(scheme: Scheme, current: str | None) -> str:
    stepper = random.Random(7)  # noqa: S311 - measurement, not secrets
    return (
        scheme.first()
        if current is None
        else scheme.next(current, step=stepper.randint(1, 50))
    )


def _random(scheme: Scheme, current: str | None) -> str:  # noqa: ARG001
    """`current` is unused; the signature has to match the other issuers."""
    return scheme.random()


def test_the_right_record_is_always_among_the_candidates() -> None:
    """The claim the whole recovery section rests on."""
    for issue in (_counted, _gapped, _random):
        _, present = _measure(issue, MEMBERS, TRIALS)
        assert present == 1.0, (issue.__name__, present)


@pytest.mark.parametrize(
    ("issue", "low", "high"),
    [
        (_random, 0.99, 1.0),
        (_counted, 0.55, 0.75),
        (_gapped, 0.90, 0.99),
    ],
)
def test_the_published_recovery_rates(issue: Issuer, low: float, high: float) -> None:
    """The README prints these as percentages. Keep the table honest."""
    exactly_one, _ = _measure(issue, MEMBERS, TRIALS)
    assert low <= exactly_one <= high, f"{issue.__name__}: {exactly_one:.1%}"


def test_the_readme_table_matches() -> None:
    from pathlib import Path

    text = (Path(__file__).resolve().parent.parent / "README.md").read_text("utf-8")
    assert "| `random()` | 100% | 100% |" in text
    assert "| `next(step=1)` | 64% | 100% |" in text
    assert "The one that was meant is always among them" in text


def _undetected_transpositions(issue: Issuer, members: int) -> tuple[int, int]:
    """Returns (swaps the check character missed, how many hit another record)."""
    scheme = Scheme()
    issued: list[str] = []
    current = None
    for _ in range(members):
        current = issue(scheme, current)
        issued.append(current)
    held = set(issued)

    missed = landed_on_somebody = 0
    for real in issued:
        flat = real.replace("-", "")
        for position in range(len(flat) - 1):
            if flat[position] == flat[position + 1]:
                continue
            swapped = (
                flat[:position]
                + flat[position + 1]
                + flat[position]
                + flat[position + 2 :]
            )
            read = scheme.parse(swapped)
            if not read.ok:
                continue  # the check character caught it
            missed += 1
            if read.value != real and read.value in held:
                landed_on_somebody += 1
    return missed, landed_on_somebody


def test_drawing_at_random_never_lands_on_another_record() -> None:
    """The reason the README tells people to use random() by default.

    The check character misses the same fraction of swaps however you issue.
    What differs is whether the miss is somebody else's identifier.
    """
    missed, landed = _undetected_transpositions(_random, 2000)
    assert missed > 0, "the check character caught everything; widen the test"
    assert landed == 0, f"{landed} of {missed} undetected swaps hit a real record"


def test_counting_densely_lands_on_another_record_often() -> None:
    """Pinned so the README's warning cannot quietly become untrue."""
    missed, landed = _undetected_transpositions(_counted, 2000)
    assert missed > 0
    assert landed / missed > 0.2, (
        f"only {landed}/{missed} landed on a record; the README warns it is much higher"
    )


def test_gaps_remove_almost_all_of_it() -> None:
    missed, landed = _undetected_transpositions(_gapped, 2000)
    assert missed > 0
    assert landed / missed < 0.1, f"{landed}/{missed} landed on a record"


def test_the_readme_carries_the_warning() -> None:
    from pathlib import Path

    text = (Path(__file__).resolve().parent.parent / "README.md").read_text("utf-8")
    assert "Why counting makes a mistyped identifier dangerous" in text
    assert "Use `random()` unless you have a reason not to" in text
