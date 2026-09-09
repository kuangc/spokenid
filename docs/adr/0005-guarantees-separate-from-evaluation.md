# 5. Exact guarantees kept separate from synthetic evaluation

Status: accepted
Date: 2026-08-24

## Context

Two kinds of number can be stated about an identifier scheme. Some are exact
and provable by enumeration: which errors the check character always detects.
Others depend on how often people make each kind of mistake, which this project
has no field data for.

Presenting the second kind with the precision of the first is how a reader ends
up trusting a figure nobody measured. Earlier drafts of the documentation
aggregated error classes into a single simulated day, which read as evidence
and was not.

## Decision

Exact guarantees are stated exactly, and verified by exhaustive tests over a
complete domain, including substitutions of the check character and swaps across
the body-and-check boundary.

Everything else goes through `benchmarks/evaluate.py`, which builds dense,
gapped and uniform cohorts from a stable SHA-256 counter stream, counts each
error class separately, and writes integer numerators and denominators to a
canonical JSON artifact with configuration and table digests. It does not
weight error classes together into an overall rate.

The committed artifact and its methodology are authoritative. Documentation may
show a generated table, labelled a deterministic evaluation rather than a study
of human error.

## Consequences

Readers get a small number of claims that are exactly true and reproducible,
instead of a larger number that sound precise.

The evaluation covers single-edit errors. Multi-symbol errors fall outside both
the guarantee and the harness, and the documentation says what that costs rather
than leaving it unstated: an escaped value is only dangerous when it is one you
issued, which is decided by how densely you allocate.

Platform-dependent timings are out of scope.
