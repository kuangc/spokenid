# spokenid

[![CI](https://github.com/kuangc/spokenid/actions/workflows/ci.yml/badge.svg)](https://github.com/kuangc/spokenid/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.10%20%E2%80%93%203.14-blue)](https://github.com/kuangc/spokenid)
[![Licence](https://img.shields.io/badge/licence-Apache--2.0-blue)](https://github.com/kuangc/spokenid/blob/main/LICENSE)

Short, fixed-length identifiers for cases where people must read an identifier
aloud, write it down, and type it back. The default looks like `4KM7-PC2K`.
Excludes A/E/I/O/U and the common letter-digit confusables, reducing accidental words and ambiguous transcription.

```python
from spokenid import Scheme

scheme = Scheme()
scheme.random()
# e.g. '7HW2-0J43'
scheme.first()
# '0000-0000'
```

This is a small identifier-format library, not an issuing service. Your database
still owns uniqueness, transactions, authorization, and the connection between an
identifier and the right record.

## When not to use this

- Use a UUID when nobody needs to say or type the value.
- Use an encoding such as [Crockford Base32](https://www.crockford.com/base32.html)
  when the text must represent an existing number or byte string.
- Use a credential or authenticated lookup when secrecy is required. A spoken ID is
  public, even when its size makes blind guessing inconvenient.
- Use a stronger or context-specific process when arbitrary multiple errors must be
  detected. The default checker has narrower guarantees described below.

## Install

Not on PyPI yet. Install the current repository with:

```bash
pip install git+https://github.com/kuangc/spokenid
```

Python 3.10 or later is required. The runtime package has no dependencies.

## Read input, then confirm repairs

`parse()` normalizes case, whitespace, and separators. It can also interpret an
excluded lookalike as the one retained character:

```python
read = scheme.parse("7hw2 oj43")
read.ok
# True
read.value
# '7HW2-0J43'
read.exact
# False
read.repairs
# (Repair(position=4, typed='o', read_as='0', column=6),)

scheme.parse("7hw2 0j43").exact
# True
```

Case and formatting do not need a correction. A lookalike repair does: require
explicit confirmation of the canonical value before a lookup or write. The repair
object says exactly what changed:

```python
for repair in read.repairs:
    print(
        f"Character {repair.column}: you typed {repair.typed}, we read {repair.read_as}"
    )
```

```
Character 6: you typed o, we read 0
```

Use `repair.column` when talking to a person: it starts at one in the raw input and
includes whitespace and separators. `Repair.position` starts at zero in the
normalized identifier, so it is useful for slicing. `Repair.typed` preserves the raw
character.

This complete lookup example never queries a repaired value:

```python
def find(typed, records):
    """Return (matches, confirmation prompt, suggestions)."""
    parsed = scheme.parse(typed)
    if parsed.exact:
        matches = [records[parsed.value]] if parsed.value in records else []
        return matches, None, ()
    if parsed.ok:
        confirmation = {
            "prompt": f"Confirm {parsed.value}, then submit it again",
            "repairs": parsed.repairs,
        }
        return [], confirmation, ()
    return [], None, scheme.suggest(typed)
```

When input is invalid, `suggest()` normalizes formatting and configured aliases, then
returns valid identifiers one supported symbol edit away. Suggestions are prompts to
confirm, not records to open:

```python
bad = scheme.parse("0000-001W")
bad.ok
# False
"0000-0012" in scheme.suggest("0000-001W")
# True
```

The result may contain no candidate or several candidates, especially when issued
identifiers are close together. Show the candidate, read it back, and require a new
exact submission before querying it.

## Issue identifiers safely

### Random issuance

`random()` uses `secrets` and does not reveal issue order. Without a `taken` callback
it draws once, so it can repeat a value issued earlier. With a callback it filters
known collisions:

```python
issued = set()
candidate = scheme.random(taken=issued.__contains__)
candidate not in issued
# True
```

The callback is convenience, not an atomic uniqueness guarantee: another writer can
insert the same candidate after the callback returns. Put a unique index on the
canonical identifier, attempt the insert, and retry after a uniqueness conflict.
After ten collisions in a row, the default call raises `SpaceExhausted` rather than
looping forever.

### Sequential issuance

`first()` and `next()` map positions in the identifier space to stable values:

```python
scheme.next("0000-0000")
# '0000-0012'
scheme.next("0000-0000", step=7)
# '0000-0078'
```

Counted references remain enumerable even when their steps vary. Do not rely on larger
or varying steps for secrecy or unpredictability: counted references still reveal
issue order. Use `random()` when identifiers should not reveal issue order.

A sequence needs one serialized writer. Lock the sequence row (or use a database
sequence), calculate the next value, insert the record, and advance the stored state
in the same database transaction. A unique index remains the final guard. Passing a
larger `step` leaves persistent gaps while preserving order; it does not replace
serialization or the uniqueness constraint.

Dense and gapped sequences can produce different sets of near-miss candidates. The
deterministic evaluation below measures that structure without claiming how often
people make each error.

## Exact guarantees and limits

The default 26-character alphabet selects the bundled `Damm` checker. For a
fixed-length identifier it detects:

- every one-symbol in-alphabet substitution, including the check character; and
- every adjacent unequal-symbol transposition (every adjacent unequal-symbol swap),
  including a swap involving the check character.

Swapping two equal symbols changes nothing. Damm does not promise to detect
arbitrary multiple errors or non-adjacent swaps. Fixed-length parsing, not Damm,
rejects a single insertion or deletion of an identifier symbol; whitespace and the
configured separator are formatting and are deliberately ignored.

**What that limit costs depends on how you allocate.** Within the guarantees
above nothing slips through, so the choice does not matter. Outside them it
does. Two symbols mistyped at once escape the check character about 3% of the
time, and one symbol misheard consistently throughout escapes about 15% of the
time. An escaped value is only dangerous if it happens to be an identifier you
issued, and that is a question of spacing: allocate at random and issued values
sit far apart in the space, so an escaped value is almost never one of them;
allocate densely with `next(step=1)` and they sit adjacent, so it often is.
Measure it for your own allocation before choosing:

```python
import random

dense = Scheme()
issued, previous = [], None
for _ in range(2000):
    previous = dense.first() if previous is None else dense.next(previous)
    issued.append(previous)
held = set(issued)

collisions = 0
rng = random.Random(0)
for real in issued:
    flat = real.replace(dense.separator, "")
    wrong = list(flat)
    for position in rng.sample(range(len(flat)), 2):
        wrong[position] = rng.choice(dense.alphabet.characters)
    attempt = dense.parse("".join(wrong))
    collisions += attempt.ok and attempt.value != real and attempt.value in held
```

`random()` allocation puts `collisions` at or near zero for the same run. Use
`random()` unless the sequence itself is the point, and confirm the name on a
record before acting on it either way.

`check=True` uses Damm for a 26-character alphabet and the existing `Luhn` checker
for other supported even-sized alphabets. Luhn detects every one-symbol in-alphabet
substitution over those alphabets but not every adjacent transposition. Pass a
checker explicitly when reading an existing format:

```python
from spokenid import Luhn, SPOKEN

legacy = Scheme(check=Luhn(SPOKEN))
round(legacy.swap_detection, 3)
# 0.997
```

`Scheme(check=False)` omits the check character. `Damm(alphabet, table=...)` accepts
an expert-supplied complete table only after validating its required structure and
error-detection properties.

## Alphabet and spoken form

Twenty-six characters make up the default alphabet:

```
0123456789CDFHJKMNPQRTVWXY
```

Its repair map keeps one canonical character for each listed letter-digit pair:

| Typed | Read as |
|---|---|
| `B` | `8` |
| `G` | `6` |
| `I` | `1` |
| `L` | `1` |
| `O` | `0` |
| `S` | `5` |
| `Z` | `2` |

Six pairs are still in the alphabet and may look alike. They remain distinct
symbols; the checker detects covered one-edit errors, while `suggest()` uses the
pairs only to rank candidates:

```python
sorted("".join(sorted(pair)) for pair in SPOKEN.similar)
# ['0D', '0Q', '49', '56', '7T', 'VW']
```

Build a different alphabet when the context calls for one:

```python
from spokenid import Alphabet

digits = Alphabet.derive(drop_vowels=False, lookalikes={}, pool="0123456789")
len(digits)
# 10
Scheme(alphabet=digits, length=6).groups
# (3, 3)
```

For reading aloud, `phonetic()` uses NATO words by default and accepts replacements:

```python
from spokenid import phonetic

phonetic("4KM7-PC2K")
# '4 Kilo Mike 7, Papa Charlie 2 Kilo'
phonetic("4K", words={"K": "Kilimanjaro"})
# '4 Kilimanjaro'
```

`phonetic()` does not validate input; parse first when the value came from a person.

## Storage and sizing

Store the canonical text returned by issuance or by an exact parse.

| Concern | Recommendation |
|---|---|
| Column | `varchar(16)` leaves room for the default and modest format changes |
| Uniqueness | Enforce a unique index in the database |
| Lookup | Query `.value` only when `.exact` is true |
| Repairs | Confirm, then resubmit the canonical value before lookup or storage |
| Case | Store uppercase canonical output |

`scheme.length` is 8 and excludes the separator; `len(scheme.random())` is 9 and
includes it. With the check character, the default carries seven information symbols.
Only `random()` draws those symbols randomly; `first()` and `next()` enumerate the
same space:

```python
scheme.length
# 8
len(scheme.random())
# 9
scheme.body_length
# 7
scheme.space
# 8031810176
```

Use `describe()` to choose a length from the population and blind-guess exposure. Its
probability assumes a guess chosen uniformly from the full identifier space, without
knowing how identifiers were allocated. That is not an attacker model for a counted
sequence, whose references are enumerable:

```python
print(Scheme(length=10).describe([100_000]))
```

```
26^9 = 5,429,503,678,976 identifiers (10 characters, shown as XXX-XXX-XXXX)
  the Damm check character detects every one-symbol in-alphabet substitution and 100.0% of adjacent unequal-symbol transpositions
  at    100,000 members, a uniform full-space guess with no allocation knowledge names a real one about 1 in 54,295,037
```

`about` marks a reciprocal rounded to the nearest integer; `guess_odds()` returns the
exact fraction. These are public identifiers. Sizing reduces accidental overlap and
uniform blind-guess exposure; it is not an authorization control.

## Deterministic synthetic evaluation

The repository includes
[the methodology](https://github.com/kuangc/spokenid/blob/main/benchmarks/README.md)
and a
[versioned result artifact](https://github.com/kuangc/spokenid/blob/main/benchmarks/results/v0.1.json).
They enumerate specified edit operations over deterministic synthetic cohorts. The
integer counts are reproducible algorithm checks, not human-error frequencies, and
the cohorts carry no claim about real users or operating conditions.

The evaluation keeps substitution, adjacent transposition, insertion, and deletion
events separate. It assigns no frequency weights and reports no combined field-use
rate.

## Command line and API

The command line exposes the same operations:

```console
$ spokenid next 0000-0000
0000-0012
```

```text
spokenid new -n 3
spokenid check 7hw2-0j43
spokenid next 0000-0000 --step 7
spokenid say 4KM7-PC2K
spokenid alphabet
spokenid describe --members 250000
```

For exact input, `check` writes the canonical identifier to stdout and exits zero. If
an excluded lookalike needs repair, it exits 2 with empty stdout and writes the
candidate plus repair details to stderr. Confirm the candidate and submit that exact
canonical value again. Other invalid input exits 1 and writes suggestions to stderr.

Public names:

| Name | Purpose |
|---|---|
| `Scheme` | Format, parse, issue, suggest, and size identifiers |
| `Parsed` / `Repair` | Parse outcome and explicit repair details |
| `Alphabet` / `Excluded` / `SPOKEN` | Character sets and exclusions |
| `Damm` / `DAMM_26_TABLE` / `Luhn` | Check-character implementations |
| `phonetic` / `NATO` | Spoken rendering |
| `default_groups` | Default grouping for a length |
| `VOWELS` / `LOOKALIKES` / `SIMILAR` | Rules behind the default alphabet |
| `SpokenIdError` / `InvalidScheme` / `InvalidArgument` | Base and input errors |
| `SpaceExhausted` / `SequenceExhausted` / `Unreadable` | Issuance and reading errors |
| `__version__` | Installed package version |

Each library error inherits from `SpokenIdError` and a conventional built-in:

| Situation | Error | Also a |
|---|---|---|
| Invalid format | `InvalidScheme` | `ValueError` |
| Invalid method argument | `InvalidArgument` | `ValueError` |
| Repeated random collision | `SpaceExhausted` | `RuntimeError` |
| End of a sequence | `SequenceExhausted` | `RuntimeError` |
| Unreadable previous value | `Unreadable` | `ValueError` |

`parse()` returns `Parsed(ok=False, problem=...)` rather than raising for unreadable
input.

## Credit

[Ryan Hennig](https://github.com/ryanhennig) wrote the original at
[Antara Health](https://github.com/antarahealth), and it ran in production for
six years, issuing identifiers to members in Kenya who read them aloud to
clinicians over the phone. The alphabet is his, and so are the two rules behind
it: drop the vowels, which removes almost every accidental word and the whole
class of accidental profanity that a vowel-carrying alphabet produces, and for
each pair of characters that get confused with each other, keep one.

This package is that idea, rewritten as a standalone library.

Two ideas came from elsewhere.

[Douglas Crockford's Base32](https://www.crockford.com/base32.html) is where
the repair rule comes from. Drop the letter and keep the digit, and a
misreading has exactly one answer: an `O` was a zero, an `S` was a five. This
alphabet is a strict subset of his, so every identifier here is also a valid
Crockford string. spokenid does not encode numbers, and it maps four aliases
Crockford does not (`B→8`, `G→6`, `S→5`, `Z→2`).

[H. Michael Damm's](https://doi.org/10.17192/z2004.0516) work on totally
anti-symmetric quasigroups is the check character. His
[2006 paper](https://doi.org/10.1016/j.disc.2006.05.033) shows such quasigroups
exist for every order except 2 and 6; the bundled order-26 table is generated
from that construction and checked in the test suite.

Two more projects were useful to read.
[OpenMRS IDGEN](https://github.com/openmrs/openmrs-module-idgen) treats
identifier allocation as a database-backed service, which is why this library
takes a `taken` callback rather than assuming a database.
[Nano ID](https://github.com/ai/nanoid) and its
[dictionary](https://github.com/CyberAP/nanoid-dictionary) arrived at a
vowel-free, lookalike-free alphabet independently.

## Development

```bash
uv sync --locked
uv run --locked pytest
uv run --locked mypy
uv run --locked ruff check .
uv run --locked ruff format --check .
uv build --no-build-isolation
```

The test suite executes the README examples and derives the exact numeric claims.
See [CONTRIBUTING.md](https://github.com/kuangc/spokenid/blob/main/CONTRIBUTING.md)
and [CHANGELOG.md](https://github.com/kuangc/spokenid/blob/main/CHANGELOG.md).

## Licence

Apache-2.0. See [LICENSE](https://github.com/kuangc/spokenid/blob/main/LICENSE).
