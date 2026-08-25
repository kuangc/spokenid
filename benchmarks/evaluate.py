"""Generate deterministic, integer-counted spokenid evaluations.

This module deliberately has no source of runtime randomness. Its byte stream,
cohorts, edit events, and bounded suggestion samples are reproducible from the
versioned domain strings below.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Iterable, Iterator, Sequence, Set
from itertools import pairwise
from pathlib import Path
from typing import Any, Final, Protocol

from spokenid import DAMM_26_TABLE, Parsed, Scheme

SCHEMA_VERSION: Final = 1
TOOL_VERSION: Final = 1
STREAM_DOMAIN: Final = b"spokenid-evaluation-v1\0"
COHORT_SEED: Final = "default-v1"
SUGGESTION_SEED_TEMPLATE: Final = "suggestions/{cohort}/{error_kind}"
DAMM_TABLE_ENCODING: Final = "row-major unsigned bytes, one byte per entry"
EVALUATION_MODEL: Final = (
    "single-edit operation events: substitutions, adjacent unequal-symbol "
    "transpositions, insertions, and deletions; suggestion cases sampled "
    "uniformly without replacement"
)
ERROR_KINDS: Final = (
    "substitution",
    "adjacent_transposition",
    "insertion",
    "deletion",
)
OUTCOME_KEYS: Final = (
    "detected",
    "accepted_same",
    "accepted_unissued",
    "accepted_another_issued",
)
SUGGESTION_KEYS: Final = (
    "recovered_unique",
    "recovered_ambiguous",
    "source_missing",
)
PROFILE_CONFIGS: Final = {
    "ci": {"members": 24, "suggestion_cases_per_error_class": 8},
    "full": {"members": 1_000, "suggestion_cases_per_error_class": 128},
}


class ByteStream(Protocol):
    """The small interface rejection sampling needs from a byte stream."""

    def read(self, size: int) -> bytes:
        """Return exactly ``size`` bytes."""


class SHA256CounterStream:
    """A stable SHA-256 counter stream, not a cryptographic random generator.

    Block ``n`` is ``SHA256(domain || UTF8(seed) || NUL || uint64be(n))``.
    Seeds identify independent uses; the fixed domain and counter encoding make
    the stream portable across Python versions and operating systems.
    """

    def __init__(self, seed: str) -> None:
        self._seed = seed.encode("utf-8")
        self._counter = 0
        self._buffer = b""

    def read(self, size: int) -> bytes:
        """Return ``size`` deterministic bytes, continuing the current stream."""
        if size < 0:
            raise ValueError("size cannot be negative")
        while len(self._buffer) < size:
            block = hashlib.sha256(
                STREAM_DOMAIN + self._seed + b"\0" + self._counter.to_bytes(8, "big")
            ).digest()
            self._counter += 1
            self._buffer += block
        result, self._buffer = self._buffer[:size], self._buffer[size:]
        return result


def randbelow(stream: ByteStream, bound: int) -> int:
    """Draw from ``range(bound)`` without modulo bias.

    Values in the incomplete high tail of the byte range are discarded before
    reducing modulo ``bound``.
    """
    if not isinstance(bound, int) or isinstance(bound, bool) or bound <= 0:
        raise ValueError("bound must be a positive integer")
    width = max(1, (bound.bit_length() + 7) // 8)
    byte_space = 1 << (8 * width)
    accepted = byte_space - byte_space % bound
    while True:
        candidate = int.from_bytes(stream.read(width), "big")
        if candidate < accepted:
            return candidate % bound


def sample_without_replacement(
    population: int,
    *,
    count: int,
    stream: ByteStream,
) -> tuple[int, ...]:
    """Return ``count`` distinct positions in deterministic draw order."""
    if population < 0 or count < 0 or count > population:
        raise ValueError("count must be between zero and population")
    selected: set[int] = set()
    ordered: list[int] = []
    while len(ordered) < count:
        candidate = randbelow(stream, population)
        if candidate not in selected:
            selected.add(candidate)
            ordered.append(candidate)
    return tuple(ordered)


def dense_positions(members: int, *, space: int) -> tuple[int, ...]:
    """Return the first ``members`` positions in a counted identifier space."""
    _validate_cohort_size(members, space)
    return tuple(range(members))


def gapped_positions(
    members: int,
    *,
    space: int,
    seed: str,
) -> tuple[int, ...]:
    """Return a counted cohort with persistent SHA-derived steps from 1 to 50."""
    _validate_cohort_size(members, space)
    if members == 0:
        return ()
    stream = SHA256CounterStream(f"gapped/{seed}")
    positions = [0]
    while len(positions) < members:
        following = positions[-1] + randbelow(stream, 50) + 1
        if following >= space:
            raise ValueError("the gapped cohort exceeds the identifier space")
        positions.append(following)
    return tuple(positions)


def uniform_positions(
    members: int,
    *,
    space: int,
    seed: str,
) -> tuple[int, ...]:
    """Return SHA-derived uniform positions without replacement."""
    _validate_cohort_size(members, space)
    return sample_without_replacement(
        space,
        count=members,
        stream=SHA256CounterStream(f"uniform/{seed}"),
    )


def _validate_cohort_size(members: int, space: int) -> None:
    """Validate cohort boundaries shared by all position generators."""
    if not isinstance(members, int) or isinstance(members, bool) or members < 0:
        raise ValueError("members must be a non-negative integer")
    if not isinstance(space, int) or isinstance(space, bool) or space <= 0:
        raise ValueError("space must be a positive integer")
    if members > space:
        raise ValueError("members cannot exceed the identifier space")


def identifier_at(scheme: Scheme, position: int) -> str:
    """Map zero to ``first()`` and other positions to a step from it."""
    if not 0 <= position < scheme.space:
        raise ValueError("position is outside the identifier space")
    first = scheme.first()
    return first if position == 0 else scheme.next(first, step=position)


def fingerprint(values: Iterable[str]) -> str:
    """SHA-256 fingerprint newline-joined UTF-8 values without a final newline."""
    return hashlib.sha256("\n".join(values).encode("utf-8")).hexdigest()


def _flat(scheme: Scheme, identifier: str) -> str:
    """Remove the exact canonical separator from a canonical identifier."""
    return identifier.replace(scheme.separator, "") if scheme.separator else identifier


def error_events(scheme: Scheme, source: str, kind: str) -> Iterator[str]:
    """Yield changed single-edit events of one explicit error class.

    Events are operations, not unique resulting strings. For example, deleting
    either of two repeated adjacent symbols remains two separately counted edit
    events.
    """
    flat = _flat(scheme, source)
    characters = scheme.alphabet.characters
    if len(flat) != scheme.length:
        raise ValueError("source is not canonical for this scheme")
    if kind == "substitution":
        for position, typed in enumerate(flat):
            for replacement in characters:
                if replacement != typed:
                    yield flat[:position] + replacement + flat[position + 1 :]
        return
    if kind == "adjacent_transposition":
        for position in range(len(flat) - 1):
            if flat[position] != flat[position + 1]:
                yield (
                    flat[:position]
                    + flat[position + 1]
                    + flat[position]
                    + flat[position + 2 :]
                )
        return
    if kind == "insertion":
        for position in range(len(flat) + 1):
            for inserted in characters:
                yield flat[:position] + inserted + flat[position:]
        return
    if kind == "deletion":
        for position in range(len(flat)):
            yield flat[:position] + flat[position + 1 :]
        return
    raise ValueError(f"unknown error kind: {kind}")


def classify_parse(parsed: Parsed, source: str, issued: Set[str]) -> str:
    """Classify a parse without treating a valid unissued code as a wrong record."""
    if not parsed.ok or parsed.value is None:
        return "detected"
    if parsed.value == source:
        return "accepted_same"
    if parsed.value in issued:
        return "accepted_another_issued"
    return "accepted_unissued"


def canonical_json(value: Any) -> str:
    """Render canonical human-readable JSON with exactly one final newline."""
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _error_event_count(scheme: Scheme, sources: Sequence[str], kind: str) -> int:
    """Return the operation-event denominator for one error class."""
    if kind == "substitution":
        return len(sources) * scheme.length * (len(scheme.alphabet) - 1)
    if kind == "insertion":
        return len(sources) * (scheme.length + 1) * len(scheme.alphabet)
    if kind == "deletion":
        return len(sources) * scheme.length
    if kind == "adjacent_transposition":
        return sum(
            left != right
            for source in sources
            for left, right in pairwise(_flat(scheme, source))
        )
    raise ValueError(f"unknown error kind: {kind}")


def _suggestion_outcome(
    scheme: Scheme,
    typed: str,
    source: str,
    issued: Set[str],
) -> str:
    """Classify whether bounded suggestion recovery finds the issued source."""
    candidates = set(scheme.suggest(typed))
    if source not in candidates:
        return "source_missing"
    issued_candidates = candidates & issued
    if issued_candidates == {source}:
        return "recovered_unique"
    return "recovered_ambiguous"


def _evaluate_errors(
    scheme: Scheme,
    sources: Sequence[str],
    *,
    cohort_name: str,
    suggestion_cases: int,
) -> tuple[dict[str, dict[str, int]], dict[str, dict[str, int | str]]]:
    """Evaluate parsing and bounded suggestion recovery for one cohort."""
    issued = set(sources)
    errors: dict[str, dict[str, int]] = {}
    suggestions: dict[str, dict[str, int | str]] = {}
    for kind in ERROR_KINDS:
        denominator = _error_event_count(scheme, sources, kind)
        selected = set(
            sample_without_replacement(
                denominator,
                count=min(suggestion_cases, denominator),
                stream=SHA256CounterStream(
                    SUGGESTION_SEED_TEMPLATE.format(
                        cohort=cohort_name,
                        error_kind=kind,
                    )
                ),
            )
        )
        outcome_counts = dict.fromkeys(OUTCOME_KEYS, 0)
        suggestion_counts = dict.fromkeys(SUGGESTION_KEYS, 0)
        selected_cases: list[str] = []
        event_index = 0
        for source in sources:
            for typed in error_events(scheme, source, kind):
                outcome = classify_parse(scheme.parse(typed), source, issued)
                outcome_counts[outcome] += 1
                if event_index in selected:
                    selected_cases.append(f"{event_index}\t{source}\t{typed}")
                    recovered = _suggestion_outcome(scheme, typed, source, issued)
                    suggestion_counts[recovered] += 1
                event_index += 1
        if event_index != denominator:
            raise AssertionError("error-event denominator drifted during evaluation")
        errors[kind] = {"denominator": denominator, **outcome_counts}
        suggestions[kind] = {
            "denominator": len(selected),
            **suggestion_counts,
            "cases_sha256": fingerprint(selected_cases),
        }
    return errors, suggestions


def _table_fingerprint() -> str:
    """Fingerprint the bundled Damm table as frozen row-major bytes."""
    raw = bytes(value for row in DAMM_26_TABLE for value in row)
    return hashlib.sha256(raw).hexdigest()


def _cohort_result(
    scheme: Scheme,
    positions: Sequence[int],
    *,
    name: str,
    suggestion_cases: int,
) -> dict[str, Any]:
    """Build and evaluate one position cohort."""
    identifiers = tuple(identifier_at(scheme, position) for position in positions)
    if len(set(identifiers)) != len(identifiers):
        raise AssertionError("a position cohort generated duplicate identifiers")
    errors, suggestions = _evaluate_errors(
        scheme,
        identifiers,
        cohort_name=name,
        suggestion_cases=suggestion_cases,
    )
    return {
        "members": len(identifiers),
        "maximum_position": max(positions, default=0),
        "positions_sha256": fingerprint(str(position) for position in positions),
        "identifiers_sha256": fingerprint(identifiers),
        "errors": errors,
        "suggestions": suggestions,
    }


def evaluate(profile: str) -> dict[str, Any]:
    """Return a deterministic evaluation document for ``ci`` or ``full``."""
    if profile not in PROFILE_CONFIGS:
        raise ValueError(f"unknown profile: {profile}")
    selected = PROFILE_CONFIGS[profile]
    members = selected["members"]
    suggestion_cases = selected["suggestion_cases_per_error_class"]
    scheme = Scheme()
    positions = {
        "dense": dense_positions(members, space=scheme.space),
        "gapped": gapped_positions(members, space=scheme.space, seed=COHORT_SEED),
        "uniform": uniform_positions(members, space=scheme.space, seed=COHORT_SEED),
    }
    stream_spec = "SHA256(domain || UTF8(seed) || NUL || uint64be(counter))"
    return {
        "schema_version": SCHEMA_VERSION,
        "tool_version": TOOL_VERSION,
        "algorithm": {
            "alphabet": scheme.alphabet.characters,
            "alphabet_sha256": fingerprint((scheme.alphabet.characters,)),
            "checker": "Damm",
            "damm_table_encoding": DAMM_TABLE_ENCODING,
            "damm_table_sha256": _table_fingerprint(),
            "evaluation_model": EVALUATION_MODEL,
            "evaluation_model_sha256": fingerprint((EVALUATION_MODEL,)),
            "sha256_counter_stream": stream_spec,
            "sha256_counter_stream_domain_hex": STREAM_DOMAIN.hex(),
            "sha256_counter_stream_spec_sha256": fingerprint((stream_spec,)),
        },
        "configuration": {
            "profile": profile,
            "members": members,
            "suggestion_cases_per_error_class": suggestion_cases,
            "length": scheme.length,
            "body_length": scheme.body_length,
            "groups": list(scheme.groups),
            "separator": scheme.separator,
            "cohort_seed": COHORT_SEED,
            "suggestion_seed_template": SUGGESTION_SEED_TEMPLATE,
            "gap_step_minimum": 1,
            "gap_step_maximum": 50,
        },
        "cohorts": {
            name: _cohort_result(
                scheme,
                cohort,
                name=name,
                suggestion_cases=suggestion_cases,
            )
            for name, cohort in positions.items()
        },
    }


def _argument_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=tuple(PROFILE_CONFIGS), default="ci")
    destination = parser.add_mutually_exclusive_group()
    destination.add_argument("--output", type=Path, help="write canonical JSON")
    destination.add_argument("--check", type=Path, help="compare canonical JSON")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Generate, write, or check a deterministic evaluation document."""
    arguments = _argument_parser().parse_args(argv)
    rendered = canonical_json(evaluate(arguments.profile))
    payload = rendered.encode("utf-8")
    if arguments.check is not None:
        try:
            existing = arguments.check.read_bytes()
        except OSError as error:
            print(f"cannot read {arguments.check}: {error}", file=sys.stderr)
            return 1
        if existing != payload:
            print(
                f"{arguments.check} does not match the {arguments.profile} profile",
                file=sys.stderr,
            )
            return 1
        print(f"{arguments.check} matches the {arguments.profile} profile")
        return 0
    if arguments.output is not None:
        try:
            arguments.output.parent.mkdir(parents=True, exist_ok=True)
            arguments.output.write_bytes(payload)
        except OSError as error:
            print(f"cannot write {arguments.output}: {error}", file=sys.stderr)
            return 1
        print(f"wrote {arguments.output}")
        return 0
    sys.stdout.write(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
