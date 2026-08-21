# spokenid

[![CI](https://github.com/kuangc/spokenid/actions/workflows/ci.yml/badge.svg)](https://github.com/kuangc/spokenid/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.10%20%E2%80%93%203.14-blue)](https://github.com/kuangc/spokenid)
[![Licence](https://img.shields.io/badge/licence-Apache--2.0-blue)](LICENSE)
[![Dependencies](https://img.shields.io/badge/dependencies-none-brightgreen)](pyproject.toml)

Short identifiers people can say out loud, write on a form, and type back
correctly, like `4KM7-PC2M`. No vowels, so an identifier can never spell a word
in any language. No character that looks like another one in the set.

## Install

Not on PyPI yet. Until it is:

```bash
pip install git+https://github.com/kuangc/spokenid
```

## Start here

```python
from spokenid import Scheme

scheme = Scheme()

scheme.random()
# '7HW2-0J46'
```

Someone reads that down a phone line and the clerk hears "oh" instead of zero:

```python
read = scheme.parse("7hw2 oj46")

read.ok        # True
read.value     # '7HW2-0J46'
read.repairs   # (Repair(position=4, typed='O', read_as='0'),)
read.exact     # False — it needed a repair, so confirm before you act on it
```

`Parsed` is truthy when it worked, so `if scheme.parse(x):` reads fine. The
repairs are handed back rather than applied quietly, because changing an
identifier without saying so is how the wrong record gets opened:

```python
for repair in read.repairs:
    print(f"Position {repair.position}: you typed {repair.typed}, we read {repair.read_as}")
```

And when it is genuinely wrong, you get a sentence you can show someone:

```python
scheme.parse("7HW2-0J4X").problem
# 'this is not a valid identifier; check it for a typing mistake'
```

## From the command line

```bash
spokenid new -n 3        # make three
spokenid check 7hw2-oj46 # normalise and validate; exit 1 if it is wrong
spokenid next 0000-0000  # the next one in a counted sequence
spokenid say 4KM7-PC2M   # 4 Kilo Mike 7, Papa Charlie 2 Mike
spokenid alphabet        # the character set, and why each one is in it
spokenid describe        # how big the space is, and how guessable
```

## Storing them

An identifier is text. `parse()` accepts it with or without the separator, in
any case, and `value` always comes back in the canonical dashed form.

**Store the canonical form**, the one `parse().value` gives you. It is what
`random()` and `next()` return, so everything agrees.

| | |
|---|---|
| Column type | `varchar(16)` is roomy for the default; the default is 9 characters including the dash |
| Length | `len(scheme.random())` counts the separator. `scheme.length` does not |
| Uniqueness | Put a unique index on the column. That index is what actually guarantees uniqueness, not this library |
| Lookup | Run the user's input through `parse()` first, then query on `.value`. Never query on raw input |
| Case | Always store uppercase. `parse()` upper-cases for you |

```python
def find_member(typed):
    read = scheme.parse(typed)
    if not read.ok:
        return None, read.problem
    return Member.objects.filter(code=read.value).first(), None
```

## The alphabet

```
0123456789CDFHJKMNPQRTVWXY
```

Twenty-six characters, built from two rules rather than typed out by hand.

**No vowels.** `A E I O U` are gone, so an identifier cannot spell a word. Not in
English, and not in Kiswahili, Luo, Somali or anything else. A list of rude words
to avoid would have to be written once per language and would still be wrong;
removing the vowels needs no list at all.

**For every pair that gets confused, keep one.** The digit stays and the letter
goes, so a misreading has exactly one answer:

| Typed | Means | | Typed | Means |
|---|---|---|---|---|
| `O` | `0` | | `S` | `5` |
| `I` | `1` | | `B` | `8` |
| `L` | `1` | | `G` | `6` |
| `Z` | `2` | | | |

Keeping the digit is the part that matters. Drop *both* halves of a pair, as some
schemes do, and a typed `O` has nothing left to mean.

Ask it about any character:

```python
from spokenid import SPOKEN

SPOKEN.explain("S")
# "'S' was dropped because it looks like '5', so it reads as '5'"
```

### Building your own

```python
from spokenid import Alphabet, Scheme

# Digits only, nothing dropped for looking like anything else.
digits = Alphabet.derive(drop_vowels=False, lookalikes={}, pool="0123456789")

Scheme(alphabet=digits, length=6).random()
# '681206'
```

`derive` removes the vowels unless you say otherwise, then removes every key of
`lookalikes` and keeps every value. Keep the count even, or turn the check
character off — see below.

## Two ways to issue an identifier

### Random, when it might appear in a URL

Drawn from `secrets`, so an identifier is not predictable from the ones before
it. You supply the uniqueness check, so this library never needs to know about
your database:

```python
issued = set()

scheme.random(taken=lambda candidate: candidate in issued)
```

After ten collisions in a row it raises `SpaceExhausted` rather than looping
forever, and the message tells you the population has outgrown the scheme.

### Counting, when it must never collide

Give it the last identifier you issued and it hands back the next one. There is
no collision check to run, because counting cannot produce one:

```python
scheme.first()
# '0000-0000'

scheme.next("0000-0000")
# '0000-001X'
```

Counted identifiers sort into the order they were issued, which is useful when
they are filed on paper.

Two things to know. **This assumes a single writer**: two processes that read the
same stored value both get the same answer, so whatever holds the last issued
identifier has to serialise access to it, with a row lock or a database sequence.
And **counted identifiers are guessable**, since holding one means holding the
next. Leaving gaps helps, and costs neither the ordering nor the guarantee:

```python
import random

scheme.next("0000-001X", step=random.randint(1, 50))
```

## Choosing the length

Any length works, and the grouping follows automatically:

```python
Scheme(length=6).random()   # 'KKK-QCJ'
Scheme(length=10).random()  # '3MV-THK-5Y73'
```

```python
print(Scheme(length=10).describe([100_000]))
```

```
26^9 = 5,429,503,678,976 identifiers (10 characters, shown as XXX-XXX-XXXX)
  at    100,000 members, a blind guess names a real one 1 in 54,295,037
```

That last column is the number to choose by. A repeat drawn at random is not a
failure, because `random()` simply draws again and nobody sees it. An identifier
that is easy to guess is a way to reach someone else's record.

Note that the check character uses one of your characters, so an eight-character
identifier carries seven random ones.

## The last character catches mistakes

Like the last digit of a credit card number. It catches **every** single-character
mistake, and about 99.7% of swaps of neighbouring characters.

That guarantee needs an alphabet with an even number of characters, which is why
this one has twenty-six. Over an odd alphabet roughly one single-character
mistake in forty goes unnoticed, so `Scheme` refuses to build one rather than
quietly promising less than it delivers:

```python
from spokenid import Alphabet, InvalidScheme, Scheme

odd = Alphabet.derive(lookalikes={"I": "1", "O": "0", "B": "8", "S": "5"})
len(odd)   # 29

try:
    Scheme(alphabet=odd)
except InvalidScheme as error:
    print(error)
```

Both figures come from exhaustive enumeration, not sampling; the test is
`tests/test_check.py::test_catches_every_single_character_mistake`, which checks
1.3 million substitutions. Turn the check off with `Scheme(check=False)` if you
would rather have the extra character, and any odd alphabet then works.

## Errors

Everything this library raises inherits from `SpokenIdError`, and each one also
inherits from the built-in you would expect, so existing `except` clauses keep
working.

| Raised by | Error | Also a |
|---|---|---|
| `Scheme(...)` with impossible arguments | `InvalidScheme` | `ValueError` |
| `random()` after repeated collisions | `SpaceExhausted` | `RuntimeError` |
| `next()` past the end of the space | `SequenceExhausted` | `RuntimeError` |
| `next()` on something unreadable | `Unreadable` | `ValueError` |

`parse()` never raises. It returns a `Parsed` with `ok=False` and a `problem` you
can show someone, whatever you hand it.

## Reading it out loud

```python
from spokenid import phonetic

phonetic("4KM7-PC2M")
# '4 Kilo Mike 7, Papa Charlie 2 Mike'
```

This is a plain NATO speller and does not validate anything, so run input
through `parse()` before you read it back to someone.

## When not to use this

- **You need to encode a number.** These identifiers are drawn, not encoded. Use
  [Crockford Base32](https://www.crockford.com/base32.html), which this alphabet
  is a subset of.
- **Nobody ever types or says the identifier.** Then it should be a UUID, and the
  constraints here cost you entropy for nothing.
- **You need a secret.** An identifier is not a credential. Guessing resistance is
  a bonus; authentication is the thing that keeps records private.
- **You need every neighbour swap caught.** The check character catches almost
  all, not all. Damm's algorithm catches all and is not implemented here.

## Known limits

Six pairs are still in the alphabet that a careless reader could confuse:
`0/Q`, `0/D`, `7/T`, `V/W`, `4/9`, `5/6`. Excluding them costs more characters
than it buys, and exclusions must come in pairs to keep the count even. The check
character is what covers them.

## Prior art

[Crockford Base32](https://www.crockford.com/base32.html) solves the lookalike
problem well and has a better repair rule than anything else published, but keeps
`A` and `E`, so its identifiers can still spell words. Its one vowel exclusion,
`U`, is calibrated on an English list.
[OpenMRS](https://github.com/openmrs/openmrs-module-idgen) issues patient
identifiers with a Luhn check digit and keeps `A`, `E` and `U`; its `Mod25`
validator uses an alphabet of 25 characters.

## Development

```bash
uv sync
uv run pytest        # tests, doctests, and every example on this page
uv run mypy
uv run ruff check .
```

Changes are listed in [CHANGELOG.md](CHANGELOG.md). Contributions are welcome —
see [CONTRIBUTING.md](CONTRIBUTING.md).

## Licence

Apache-2.0. See [LICENSE](LICENSE).
