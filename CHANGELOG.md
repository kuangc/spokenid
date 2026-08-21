# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project uses
[semantic versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-08-17

First release.

### Added

- `Scheme`, which describes the shape of an identifier and issues one two ways:
  `random()` with a caller-supplied uniqueness check, and `next()` which counts
  and therefore cannot collide.
- `parse()`, which fixes case and spacing, reinterprets characters that were
  dropped for looking like ones that were kept, and reports every
  reinterpretation instead of applying it silently.
- `SPOKEN`, a 26-character alphabet with no vowels, so an identifier cannot
  spell a word in any language. A strict subset of Crockford Base32.
- `Alphabet.derive()`, which builds an alphabet from exclusion rules so that the
  characters and the repair table cannot drift apart.
- A Luhn check character, which refuses to be built over an odd alphabet rather
  than quietly failing to catch every single-character mistake.
- `phonetic()`, for reading an identifier aloud.
- `describe()`, which reports how large a scheme is and how guessable an
  identifier is at a given population.

[Unreleased]: https://github.com/kuangc/spokenid/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/kuangc/spokenid/releases/tag/v0.1.0
