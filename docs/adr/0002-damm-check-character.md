# 2. Damm rather than Luhn as the default check character

Status: accepted
Date: 2026-08-24

## Context

The first implementation used Luhn mod N. Luhn detects every single-symbol
substitution, but only over an alphabet with an even number of characters, and
it does not detect every transposition of neighbouring symbols. Over the default
26-character alphabet it misses about three neighbour swaps in a thousand, and
every non-adjacent swap.

Damm's algorithm detects both, given a totally anti-symmetric quasigroup of the
right order. Such quasigroups exist for every order except 2 and 6.

## Decision

`check=True` selects a bundled Damm checker for a 26-character alphabet, and
the existing Luhn checker for other supported even alphabets. `Damm` and `Luhn`
can both be passed explicitly, and must use the same alphabet as their scheme.

The order-26 table is generated from Damm's published construction rather than
pasted in as an unexplained matrix: build `GF(25) = F5[s]/(s²-2)`, take
`α = 3+3s`, `β = 3+2s`, `x ⋆ y = αx + βy + 1`, prolong with an infinity element,
and relabel. Sourced to Damm's [2004 dissertation](https://doi.org/10.17192/z2004.0516)
and his [2007 existence theorem](https://doi.org/10.1016/j.disc.2006.05.033).

`Damm(alphabet, table=...)` accepts an expert-supplied table, validating
dimensions, Latin rows and columns, a zero diagonal and weak total
anti-symmetry before use. Omitting `table` works only at order 26, rather than
pretending a 26-row table can be truncated for a smaller alphabet.

## Consequences

Every single-symbol substitution and every adjacent unequal-symbol transposition
is detected, including at the check character. Non-adjacent swaps, which Luhn
never caught, are detected almost always.

Damm is not uniformly better. Where one symbol is misread *consistently*
throughout an identifier — a plausible error when reading aloud — Damm lets
about 15% through against Luhn's 3%. End to end the difference is small, because
what dominates is whether an escaped value happens to be an identifier you
issued, and that is decided by allocation rather than by the check character.
Luhn remains available for that reason and for reading an existing format.

The table is data. Golden vectors and a digest guard it against accidental
change. It is validated once at import, not per `Scheme()`.
