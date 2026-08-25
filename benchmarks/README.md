# Deterministic evaluation

This directory contains a reproducible **synthetic** evaluation of `spokenid`.
It tests declared algorithm behavior against constructed identifier cohorts. It is
not a human-error frequency study, and its counts must not be read as estimates of
how often people make each kind of mistake.

The evaluator uses only Python's standard library and the local `spokenid` package.
Run the small profile during development:

```console
uv run --locked python benchmarks/evaluate.py --profile ci
```

Verify the committed v0.1 artifact before changing it:

```console
uv run --locked python benchmarks/evaluate.py --profile full --check benchmarks/results/v0.1.json
```

When an intentional algorithm or configuration change requires regeneration, write
the artifact, review its exact diff, and check a fresh evaluation against it:

```console
uv run --locked python benchmarks/evaluate.py --profile full --output benchmarks/results/v0.1.json
git diff -- benchmarks/results/v0.1.json
uv run --locked python benchmarks/evaluate.py --profile full --check benchmarks/results/v0.1.json
```

`--check` compares canonical JSON bytes, so it catches changes to configuration,
cohorts, algorithms, counts, or serialization. The artifact intentionally contains
no timestamp, machine details, floating-point rate, or timing measurement.

## Profiles and scheme

Both profiles use the default eight-symbol scheme: seven information symbols, the
bundled order-26 Damm check symbol, groups `4-4`, and the default 26-character
alphabet. The `ci` profile uses 24 identifiers per cohort and 8 suggestion cases per
error class. The practical `full` profile uses 1,000 identifiers per cohort and 128
suggestion cases per error class.

Every identifier comes from an integer position in the scheme space. Position zero
maps to `first()`; position *n* maps to `next(first(), step=n)`. The three cohorts are:

- **dense:** positions `0..members-1`;
- **gapped:** position zero followed by persistent SHA-256-derived steps from 1 to
  50; and
- **uniform without replacement:** SHA-256-derived positions sampled across the
  complete scheme space, rejecting duplicate draws.

There is no call to a runtime pseudorandom or secret generator. Block *n* of the
versioned counter stream is below. `domain` is the UTF-8 encoding of
`spokenid-evaluation-v1` followed by NUL; the artifact also stores those exact bytes
as hexadecimal.

```text
SHA256(domain || UTF8(seed) || NUL || uint64be(n))
```

Rejection sampling discards the incomplete high tail before reducing a draw modulo
its bound. This avoids modulo bias and produces identical results across supported
Python versions and operating systems. The artifact records the `default-v1` cohort
seed and the `suggestions/{cohort}/{error_kind}` seed template used for bounded
recovery cases.

Position and identifier fingerprints are SHA-256 digests of newline-joined values
encoded as UTF-8, without a final newline. The Damm table digest uses the project's
frozen **row-major unsigned bytes, one byte per entry** encoding: concatenate all 26
rows without a separator, then apply SHA-256. The artifact stores the exact
`evaluation_model` UTF-8 string beside `evaluation_model_sha256`, allowing consumers
to recompute that digest directly. It also records alphabet, stream-specification,
suggestion-case, and corpus fingerprints.

## Error events and outcomes

The evaluator keeps four error classes separate:

1. replacing one symbol with any other alphabet symbol;
2. transposing one adjacent unequal-symbol pair;
3. inserting one alphabet symbol at any position; and
4. deleting one symbol at any position.

These are operation events, not deduplicated strings. Deleting the first or second
symbol in a repeated pair counts as two events even if both operations produce the
same text. This convention makes every denominator derivable from the corpus and
the stated edit model.

Each event has exactly one parse outcome:

- `detected`: parsing rejects it;
- `accepted_same`: parsing accepts the original issued identifier;
- `accepted_unissued`: parsing accepts a valid identifier outside the cohort; or
- `accepted_another_issued`: parsing accepts a different cohort member.

The distinction between the last two is important: a syntactically valid but
unissued identifier is not evidence that a wrong record would be opened.

Calling `suggest()` for every event would add work without changing the exact Damm
guarantees. For each cohort and error class, the evaluator instead selects a bounded
uniform sample of operation-event indexes using an independently seeded SHA-256
stream. The artifact records that sample's own denominator and fingerprint. Its
exclusive outcomes are `recovered_unique`, `recovered_ambiguous`, and
`source_missing`, based only on candidates that are members of the synthetic
cohort.

## Interpretation limits

The substitution and transposition checks model in-alphabet single edits. An equal
adjacent swap is not an edit because it leaves the text unchanged. Insertion and
deletion rejection follows from fixed length. This evaluation does not assign human
frequency weights, combine classes into a "realistic" aggregate, cover arbitrary
multiple errors or non-adjacent swaps, or measure field usability. Human performance
requires appropriately designed research with real users and contexts.
