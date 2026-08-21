# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project uses
[semantic versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

Nothing has been released yet. Everything below ships in the first release.

### Added

- `RELEASING.md`, and gates so the documentation cannot lag a tag: the suite
  fails if a version is tagged with no changelog section, or if the README
  still says the package is not on PyPI once something is published. That text
  is what renders on the PyPI page.
- The release workflow runs the full suite on every supported Python and uses
  the built wheel from a clean environment before it publishes anything. It
  used to build and publish without a single test.

- `Scheme.suggest()`, which answers the question `parse()` leaves open. When
  somebody mistypes an identifier at a counter, it returns the valid
  identifiers one mistake away. The check character keeps that list short:
  about one candidate per character, rather than a haystack.
- `Repair.column`, the position counting from one and including separators,
  which is the number to show a person. `Repair.position` still indexes the
  identifier for slicing.
- `Alphabet.similar` and `SIMILAR`: the pairs that stay confusable inside an
  alphabet. `suggest()` ranks a near miss that looks like a misreading above
  one that does not, and the README's list of known limits is now read from
  the code rather than typed out beside it.
- `phonetic(words=...)`, so somewhere NATO is not the words people know can
  pass its own.
- `spokenid new --plain`, and near misses on a failed `spokenid check`.

### Fixed

- **Counting and drawing at random differ by far more than the README said.**
  No check character catches every mistake, and counted identifiers sit next to
  each other, so an undetected error often lands on another identifier you
  issued. Measured over a register of five thousand: of the neighbour swaps the
  check character misses, half hit another real record when counting with
  `step=1`, and none do when drawing at random. Over a simulated day of forty
  thousand lookups, counting returns the wrong record 0.64% of the time and
  random returns it never. The README presented the choice as collision-freedom
  against guessability; it now leads with this, recommends `random()` by
  default, and shows the numbers.
- `random()` without a `taken` check draws once and can return an identifier
  you already issued, while the README said it "simply draws again". It says
  what actually happens now, and `spokenid new -n N` de-duplicates its own
  batch.
- `Scheme(check="no")` and `Scheme(check=None)` quietly built a scheme with no
  check character.
- `Alphabet.derive` silently ignored a lookalike whose key was not in the pool.
- The release gates read `git tag -l` from the checkout, but actions/checkout
  does not fetch tags for a branch or pull-request build, so tagging a release
  would have turned CI red on main permanently. Those checks moved into
  `release.yml`, where the tag exists.
- `RELEASING.md` gave an order that could not be followed and never said to
  commit the edits, so the tag would have landed on a commit without them.

- The recovery recipe in the README insisted on exactly one candidate and
  returned nothing otherwise. When identifiers are issued by counting — which
  the README recommends for paper filing — neighbours are dense, so at a
  thousand members a third of mistyped identifiers had two or three candidates
  the clinic held and the recipe threw all of them away. The identifier that
  was meant is among the candidates every time; the recipe hands them back now,
  the rates are published as a table, and the advice to leave gaps is connected
  to recovery rather than only to guessing resistance.
- Group sizes were not type-checked the way `length` is, so `groups=(4.0, 4.0)`
  built a scheme on which every method raised `TypeError`.

- The broken-pipe fix only covered output large enough to overflow the 8 KB
  buffer, so eight of nine subcommands still exited 120 with a traceback when
  their reader went away. The flush happens where the handler can see it now,
  both streams are redirected, and argparse's own exit path is covered. There
  is a test.
- `Scheme(length=...)` computed the grouping before checking the length, so an
  enormous number raised `OverflowError` or allocated over a gigabyte before
  reaching the guard. It is checked first, and a length that is not a whole
  number is refused rather than failing later.
- An `Alphabet` accepted two exclusions for the same character, after which
  `explain()` reported the first and `parse()` applied the last. The alphabet
  could tell a clerk `O` meant `0` while resolving it to something else.

- **`parse()` silently misread input.** The early exit added to bound reading
  cost counted separator characters before they were removed, so anything of
  the form `<identifier><three or more separators><anything>` had its tail
  discarded and was accepted. `parse("0000-001X --- Jane Doe")` returned
  `ok=True` with the identifier, `validate()` agreed, and the command line
  exited 0. Worse, input could be truncated into a *different* valid
  identifier: `parse("0-311-PF-H-V1")` returned `0311-PFHV`. Nothing is counted
  until the separators are out, so trailing content is refused again and
  separator padding parses as it used to.
- `suggest()` cut the list at ten by default, and generates substitutions left
  to right, so the position it dropped first was the last one, which is the
  check character. A mistyped check character is one of the likeliest errors,
  and the right answer was missing 42% of the time at sixteen characters. All
  candidates are returned now; there are only about as many as the identifier
  is long.
- The command line died with a `BrokenPipeError` traceback and exit 120 when
  its output was closed early, which is what `| head` does. It exits 141 in
  silence, as a well-behaved command should.

- **A separator could still be accepted and then break the scheme.** The first
  attempt at this fixed the comparison but not the disagreement underneath it:
  the check read the separator as written while reading upper-cased it, so
  eighteen lower-case separators passed and then deleted a body character.
  `Scheme(separator="x")` issued identifiers it could not read back two steps
  later. Both sides now fold case the same way, and a separator that mixes
  whitespace with anything else is refused, because reading strips whitespace
  first and such a separator could never match.
- `describe()` and `random()` raised a bare `ValueError` for a scheme longer
  than about 3,040 characters, because Python refuses to render an integer of
  more than 4,300 digits. Length is now capped at 256, which is far past
  anything a person would read aloud.
- The cap on input length measured what was pasted rather than what it
  contained, so a valid identifier behind a lot of padding was refused. Reading
  now stops as soon as the result is too long to be an identifier, which makes
  a twenty-megabyte paste cost the same as a short one and accepts the padded
  identifier.
- A scheme with a long separator could not read back its own output.
- `Luhn.verify()` raised `TypeError` for input that was not text, though it
  promises an answer.

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

### Everything else in the first release

- `tests/test_readme_figures.py`. A reviewer smuggled nine wrong figures past
  the README test, because it only checked code blocks and every number written
  in a sentence was unchecked. The figures are recomputed from the library now,
  and the same nine changes all fail. Values shown as `# comment` are compared
  whether they sit on the same line or the next, and `$ spokenid` blocks are
  executed rather than taken on trust.

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

[Unreleased]: https://github.com/kuangc/spokenid/commits/main/
