# 3. Repairs are reported, never applied silently

Status: accepted
Date: 2026-08-24

## Context

The alphabet is chosen so that a misread character has exactly one plausible
correction ([0001](0001-vowel-free-alphabet.md)). That makes it tempting to
apply the correction and return the identifier, which is what most parsers do
with normalization.

Quietly changing an identifier is how the wrong record gets opened. Case and
spacing are different: they carry no information, so fixing them silently costs
nothing.

## Decision

`parse()` returns a `Parsed` carrying every reinterpretation in `repairs`, and
`exact` is true only when nothing had to be reinterpreted. Case, whitespace and
an omitted separator are normalized silently and leave `exact` true.

`Repair` describes what the person actually did: `typed` keeps the original
character and case, `column` is the one-based column in the raw input including
separators, and `position` is the zero-based symbol in the canonical identifier.
Repairs stay attached to a failed result too, so a caller can explain a
rejection.

`next()` refuses a previous identifier that needed a repair, rather than
advancing from a value it guessed at.

## Consequences

Callers must decide what to do with a repaired read. The intended workflow is
that `exact` means look it up, and not exact means confirm with the person
first.

`repair.column` is the number to show someone, because it matches what they are
looking at; `position` is for slicing. Both exist because using one for the
other is an off-by-one on every repair message.
