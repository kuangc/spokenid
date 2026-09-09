# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project uses
[semantic versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0]

- Generate fixed-length identifiers randomly or as serialized sequences, with
  configurable grouping, separators, alphabets, and check characters. Random
  drawing raises `SpaceExhausted` when its retry budget runs out, which does not
  by itself mean the namespace is full.
- Use a validated order-26 Damm checker by default, detecting every one-symbol
  in-alphabet substitution and every adjacent unequal-symbol transposition.
- Parse case and formatting, preserve the raw location of lookalike repairs, and
  require callers to distinguish exact input from proposed corrections:
  `Parsed.status` is `exact`, `confirmation_required` or `invalid`, `bool(parsed)`
  raises so a repaired candidate cannot slip past an `if parsed` guard, and
  `Scheme.is_canonical()` checks stored text without normalizing it.
- Suggest valid identifiers one substitution, adjacent transposition, insertion, or
  deletion away from invalid input.
- Report exact identifier-space, blind-guess, and adjacent-transposition properties
  without floating-point underflow.
- Provide command-line generation, checking, sequential allocation, spoken rendering,
  alphabet inspection, and sizing.
- Include a deterministic synthetic evaluation artifact, property tests, strict type
  checking, and executable README examples.
