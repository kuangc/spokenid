"""Deterministic, auditable evaluation tooling."""

from __future__ import annotations

import hashlib
import json
from itertools import pairwise
from pathlib import Path

import benchmarks.evaluate as evaluator
import pytest
from benchmarks.evaluate import (
    ERROR_KINDS,
    OUTCOME_KEYS,
    SUGGESTION_KEYS,
    SHA256CounterStream,
    canonical_json,
    classify_parse,
    dense_positions,
    error_events,
    evaluate,
    fingerprint,
    gapped_positions,
    identifier_at,
    randbelow,
    sample_without_replacement,
    uniform_positions,
)

from spokenid import Scheme

ROOT = Path(__file__).resolve().parents[1]
FULL_ARTIFACT = ROOT / "benchmarks" / "results" / "v0.1.json"


class _Bytes:
    """A byte source that makes rejection behavior observable."""

    def __init__(self, value: bytes) -> None:
        self.value = value

    def read(self, size: int) -> bytes:
        assert size == 1
        head, self.value = self.value[:1], self.value[1:]
        return head


def test_sha256_counter_stream_has_a_stable_domain_separated_sequence() -> None:
    stream = SHA256CounterStream("unit-test")

    assert stream.read(40).hex() == (
        "5b16fc2718f26d23ac0d4426775b248e8e8fe1c80fce7ad9e9fe7863155bcbb02fcb7a6749fd01c1"
    )


def test_randbelow_discards_biased_tail_values() -> None:
    assert randbelow(_Bytes(b"\xff\x07"), 10) == 7


def test_position_generators_are_bounded_unique_and_reproducible() -> None:
    assert dense_positions(5, space=100) == (0, 1, 2, 3, 4)

    gapped = gapped_positions(8, space=1_000, seed="cohort")
    assert gapped == gapped_positions(8, space=1_000, seed="cohort")
    assert gapped[0] == 0
    assert all(1 <= right - left <= 50 for left, right in pairwise(gapped))
    assert len(set(gapped)) == len(gapped)

    uniform = uniform_positions(20, space=101, seed="cohort")
    assert uniform == uniform_positions(20, space=101, seed="cohort")
    assert len(uniform) == len(set(uniform)) == 20
    assert all(0 <= position < 101 for position in uniform)


def test_sampling_without_replacement_rejects_duplicate_draws() -> None:
    picked = sample_without_replacement(
        8,
        count=8,
        stream=SHA256CounterStream("complete-small-space"),
    )

    assert set(picked) == set(range(8))


def test_positions_map_to_the_public_counted_sequence() -> None:
    scheme = Scheme()
    first = scheme.first()

    assert identifier_at(scheme, 0) == first
    assert identifier_at(scheme, 1) == scheme.next(first)
    assert identifier_at(scheme, 97) == scheme.next(first, step=97)


def test_fingerprint_is_newline_joined_utf8_without_a_trailing_newline() -> None:
    expected = hashlib.sha256(b"0000-0000\n0000-0012").hexdigest()

    assert fingerprint(("0000-0000", "0000-0012")) == expected


@pytest.mark.parametrize(
    ("kind", "expected"),
    [
        ("substitution", 3 * 25),
        ("adjacent_transposition", 2),
        ("insertion", 4 * 26),
        ("deletion", 3),
    ],
)
def test_error_classes_are_separate_changed_edit_events(
    kind: str,
    expected: int,
) -> None:
    scheme = Scheme(length=3, groups=(3,), separator="")
    source = scheme.next(scheme.first())
    events = tuple(error_events(scheme, source, kind))

    assert len(events) == expected
    assert all(event != source for event in events)


def test_parse_outcomes_distinguish_unissued_from_another_issued_record() -> None:
    scheme = Scheme()
    source = scheme.first()
    other = scheme.next(source)
    unissued = scheme.next(other)

    assert classify_parse(scheme.parse(unissued), source, {source, other}) == (
        "accepted_unissued"
    )
    assert classify_parse(scheme.parse(other), source, {source, other}) == (
        "accepted_another_issued"
    )
    assert classify_parse(scheme.parse(source), source, {source, other}) == (
        "accepted_same"
    )
    assert classify_parse(scheme.parse("W" + source[1:]), source, {source, other}) == (
        "detected"
    )


def test_canonical_json_sorts_every_mapping_and_has_one_final_newline() -> None:
    rendered = canonical_json({"z": {"b": 2, "a": 1}, "a": 0})

    assert rendered == '{\n  "a": 0,\n  "z": {\n    "a": 1,\n    "b": 2\n  }\n}\n'
    assert json.loads(rendered) == {"a": 0, "z": {"a": 1, "b": 2}}


def test_ci_profile_is_repeatable_self_describing_and_integer_counted() -> None:
    first = evaluate("ci")
    second = evaluate("ci")

    assert first == second
    assert first["schema_version"] == 1
    assert first["tool_version"] == 1
    assert first["configuration"]["profile"] == "ci"
    assert set(first["cohorts"]) == {"dense", "gapped", "uniform"}
    assert first["algorithm"]["damm_table_encoding"] == (
        "row-major unsigned bytes, one byte per entry"
    )
    assert first["algorithm"]["damm_table_sha256"] == (
        "a0610f93f3294c2a271d3bc2f84dc5a84ffcea024c6c5eb7cd7ea996f7afa144"
    )
    model = first["algorithm"]["evaluation_model"]
    assert (
        hashlib.sha256(model.encode("utf-8")).hexdigest()
        == (first["algorithm"]["evaluation_model_sha256"])
    )
    assert first["algorithm"]["evaluation_model_sha256"] == (
        "e664af6f7fc8bbc2ad1ddffcbefc894ff4af93cc2e43c82262e372347601ca65"
    )
    assert first["algorithm"]["sha256_counter_stream_domain_hex"] == (
        b"spokenid-evaluation-v1\0".hex()
    )
    assert first["configuration"]["cohort_seed"] == "default-v1"
    assert first["configuration"]["suggestion_seed_template"] == (
        "suggestions/{cohort}/{error_kind}"
    )

    for cohort in first["cohorts"].values():
        assert len(cohort["identifiers_sha256"]) == 64
        assert len(cohort["positions_sha256"]) == 64
        assert cohort["members"] == first["configuration"]["members"]
        assert set(cohort["errors"]) == set(ERROR_KINDS)
        assert set(cohort["suggestions"]) == set(ERROR_KINDS)
        for counts in cohort["errors"].values():
            assert set(counts) == {"denominator", *OUTCOME_KEYS}
            assert all(type(value) is int for value in counts.values())
            assert counts["denominator"] == sum(counts[key] for key in OUTCOME_KEYS)
        for counts in cohort["suggestions"].values():
            assert set(counts) == {"denominator", "cases_sha256", *SUGGESTION_KEYS}
            assert len(counts["cases_sha256"]) == 64
            assert all(
                type(counts[key]) is int for key in ("denominator", *SUGGESTION_KEYS)
            )
            assert counts["denominator"] == (
                counts["recovered_unique"]
                + counts["recovered_ambiguous"]
                + counts["source_missing"]
            )


def test_evaluator_source_does_not_use_runtime_randomness() -> None:
    source = (
        Path(__file__).resolve().parents[1] / "benchmarks" / "evaluate.py"
    ).read_text("utf-8")

    assert "random.Random" not in source
    assert "import random" not in source
    assert "secrets" not in source


def test_cli_writes_and_checks_canonical_profile_artifacts(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    artifact = tmp_path / "nested" / "ci.json"
    expected = canonical_json(evaluate("ci")).encode("utf-8")

    assert evaluator.main(["--profile", "ci", "--output", str(artifact)]) == 0
    assert artifact.read_bytes() == expected
    assert evaluator.main(["--profile", "ci", "--check", str(artifact)]) == 0
    assert "matches the ci profile" in capsys.readouterr().out

    artifact.write_bytes(expected.replace(b"\n", b"\r\n"))
    assert evaluator.main(["--profile", "ci", "--check", str(artifact)]) == 1
    assert "does not match" in capsys.readouterr().err

    existing_directory = tmp_path / "already-a-directory"
    existing_directory.mkdir()
    assert evaluator.main(["--profile", "ci", "--output", str(existing_directory)]) == 1
    assert "cannot write" in capsys.readouterr().err


def test_committed_full_artifact_matches_the_canonical_full_profile() -> None:
    expected = canonical_json(evaluate("full")).encode("utf-8")

    assert FULL_ARTIFACT.read_bytes() == expected


def test_source_distribution_includes_the_benchmark_tree() -> None:
    pyproject = (Path(__file__).resolve().parents[1] / "pyproject.toml").read_text(
        "utf-8"
    )
    sdist = pyproject.split("[tool.hatch.build.targets.sdist]", 1)[1].split(
        "[tool.pytest.ini_options]", 1
    )[0]

    assert '"benchmarks"' in sdist


def test_configured_strict_mypy_includes_the_evaluator() -> None:
    pyproject = (Path(__file__).resolve().parents[1] / "pyproject.toml").read_text(
        "utf-8"
    )
    mypy = pyproject.split("[tool.mypy]", 1)[1]

    assert 'files = ["src", "tests", "benchmarks", "scripts"]' in mypy


def test_methodology_labels_results_synthetic_and_gives_reproduction_commands() -> None:
    methodology = (
        Path(__file__).resolve().parents[1] / "benchmarks" / "README.md"
    ).read_text("utf-8")

    assert "synthetic" in methodology.lower()
    assert "human-error frequency" in methodology
    assert "SHA-256" in methodology
    assert "row-major unsigned bytes" in methodology
    assert "evaluation_model" in methodology
    assert "uniform without replacement" in methodology
    assert "--profile full --output benchmarks/results/v0.1.json" in methodology
    assert "--profile full --check benchmarks/results/v0.1.json" in methodology
    assert methodology.index("--profile full --check") < methodology.index(
        "--profile full --output"
    )
    assert "git diff -- benchmarks/results/v0.1.json" in methodology
