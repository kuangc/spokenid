# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project uses
[semantic versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed

- A separator was checked against the alphabet with `in`, which is a substring
  test, so `separator="YX"` was accepted where `"XY"` was refused. A scheme
  could then issue identifiers its own `parse()` rejected. Separators are now
  compared character by character, against the repair characters as well.
- `Alphabet` validated a repair target the same way, so `{"B": ""}` and
  `{"B": "12"}` were accepted. An empty target made `parse()` read arbitrary
  junk as a valid identifier.
- A lower-case alphabet was accepted but could never be read back, and
  `drop_vowels` silently did nothing for a lower-case pool because the vowel set
  was upper case only. `derive` now folds case, and `Alphabet` refuses
  characters that are lower case, whitespace, or unprintable.
- `I` and `O` were reported with `reason="vowel"` while `explain()` called them
  lookalikes. They are described as lookalikes now, which is the useful half.
- `guess_odds()` raised `OverflowError` for a very large population, and
  `describe()` printed "never" for a space so large the odds underflowed.
  Both count in integers now.
- `Luhn.verify()` raised instead of answering for input outside the alphabet.
- `phonetic()` raised on the empty separator that `Scheme` accepts.
- `parse()` rebuilt the repair table once per character and checked the length
  only after scanning everything, so a pasted megabyte took 739ms. It now
  refuses over-long input up front and takes 0.1ms.
- A character whose upper case is two characters, such as `ß`, produced two
  repairs at positions that did not exist in what the person typed.
- Argument errors raised a bare `ValueError`. Every error this library raises
  now inherits from `SpokenIdError`, as the documentation claimed.

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
- A command line: `spokenid new`, `check`, `next`, `say`, `describe` and
  `alphabet`.

[Unreleased]: https://github.com/kuangc/spokenid/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/kuangc/spokenid/releases/tag/v0.1.0
