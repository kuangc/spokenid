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
# e.g. '7HW2-0J46'
```

Someone reads that down a phone line and the clerk hears "oh" instead of zero:

```python
read = scheme.parse("7hw2 oj46")

read.ok
# True
read.value
# '7HW2-0J46'
read.repairs
# (Repair(position=4, typed='O', read_as='0', column=6),)
```

`Parsed` is truthy exactly when `ok` is, so `if scheme.parse(x):` reads fine.

Two different things can be wrong with what somebody types, and `exact` tells
them apart. **Case and spacing are free**; a character swapped for one that
looks like it is not:

```python
scheme.parse("7HW2-0J46").exact  # already right
# True
scheme.parse("7hw2 0j46").exact  # only case and spacing
# True
scheme.parse("7hw2 oj46").exact  # an O was read as a zero
# False
```

Build the workflow on that. Exact means look it up. Not exact means read it back
to the person first, which is why the repairs are handed to you rather than
applied quietly:

```python
for repair in read.repairs:
    print(
        f"Character {repair.column}: you typed {repair.typed}, we read {repair.read_as}"
    )
```

```
Character 6: you typed O, we read 0
```

Use `repair.column` when talking to a person: it counts from one and includes
the dashes, so it matches what they are looking at. `repair.position` indexes
the identifier without separators, for slicing.

## When it is genuinely wrong

```python
scheme.parse("7HW2-0J4X").problem
# 'this is not a valid identifier; check it for a typing mistake'
```

On its own that is a dead end, with somebody standing at the counter. So ask for
the near misses:

```python
scheme.suggest("7HW2-0J4X")
# e.g. ('DHW2-0J4X', '7TW2-0J4X', '7HJ2-0J4X')
```

Those are the identifiers one small mistake away that the check character still
accepts: a substitution, a swap of neighbours, or one character too few or too
many. There are only ever about as many as the identifier is long, because the
check character rejects the other twenty-five in twenty-six. Look them up.
Nearly always exactly one is a record you hold, and that is the answer:

```python
def find(typed, records):
    read = scheme.parse(typed)
    if read.ok:
        return records.get(read.value)
    near = [c for c in scheme.suggest(typed) if c in records]
    return records[near[0]] if len(near) == 1 else None
```

## From the command line

```bash
spokenid new -n 3               # make three
spokenid new --plain            # no dashes, for piping
spokenid check 7hw2-oj46        # normalise and validate; exit 1 if it is wrong
spokenid next 0000-0000         # the next in a counted sequence
spokenid next 0000-0000 --step 7
spokenid say 4KM7-PC2M          # 4 Kilo Mike 7, Papa Charlie 2 Mike
spokenid alphabet               # the character set, and why each one is in it
spokenid describe --members 250000
```

`new`, `check`, `next` and `describe` all take `--length N` and `--no-check`.
`check` writes the identifier to stdout and any repairs or near misses to
stderr, so it pipes cleanly. A failed `check` suggests near misses too:

```console
$ spokenid check 0000-001W
this is not a valid identifier; check it for a typing mistake
  did you mean H000-001W?
  ...
  did you mean 0000-001X?
```

## Storing them

An identifier is text. `parse()` accepts it with or without the separator, in
any case, and `value` always comes back in the canonical dashed form.

**Store the canonical form**, the one `parse().value` gives you. It is what
`random()` and `next()` return, so everything agrees.

| | |
|---|---|
| Column type | `varchar(16)` is roomy for the default, which is 9 characters including the dash |
| Length | `scheme.length` is 8 and excludes the separator; `len(scheme.random())` is 9 and includes it |
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
# e.g. '406-603'
```

`derive` removes the vowels unless you say otherwise, then removes every key of
`lookalikes` and keeps every value. Keys and values are single characters, the
pool is folded to upper case, and the count needs to stay even unless you turn
the check character off.

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

Any length works, and the grouping follows from it:

```python
Scheme(length=6).groups
# (3, 3)
Scheme(length=10).groups
# (3, 3, 4)
Scheme(length=6).random()  # e.g. 'KKK-QCJ'
```

Set `groups` and `separator` yourself when the identifier has to fit boxes
already printed on a form:

```python
scheme_for_forms = Scheme(length=9, groups=(3, 3, 3), separator=" ")
scheme_for_forms.first()
# '000 000 000'
scheme_for_forms.length
# 9
```

```python
print(Scheme(length=10).describe([100_000]))
```

```
26^9 = 5,429,503,678,976 identifiers (10 characters, shown as XXX-XXX-XXXX)
  at    100,000 members, a blind guess names a real one 1 in 54,295,036
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
len(odd)  # 29

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
| `Scheme(...)` or `Alphabet(...)` that cannot exist | `InvalidScheme` | `ValueError` |
| An argument outside what a method accepts | `InvalidArgument` | `ValueError` |
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

NATO by default, which is not much use where those are not the words people
know. Pass your own:

```python
phonetic("4K", words={"K": "Kilimanjaro"})
# '4 Kilimanjaro'
```

It does not validate anything, so run input through `parse()` before reading it
back to someone.

## Everything that is public

If it is not in this table it is an internal detail, and it may change.

| Name | What it is |
|---|---|
| `Scheme` | The shape of an identifier, and the two ways to issue one |
| `Scheme.random` / `.next` / `.first` | Issue one |
| `Scheme.parse` / `.validate` / `.suggest` | Read one back |
| `Scheme.describe` / `.space` / `.guess_odds` | Size a scheme before choosing |
| `Parsed` | What `parse()` returns: `ok`, `value`, `repairs`, `problem`, `exact` |
| `Repair` | One character read as another: `column`, `position`, `typed`, `read_as` |
| `Alphabet` / `Alphabet.derive` | The character set, and how to build another |
| `SPOKEN` | The default alphabet |
| `Alphabet.explain` / `.repairs` / `.similar` / `.sorts_by_age` | Ask it about itself |
| `phonetic` / `NATO` | Spell one for reading aloud |
| `Luhn` | The check character, if you want it on its own |
| `default_groups` | How a length turns into groups |
| `VOWELS` / `LOOKALIKES` / `SIMILAR` | The rules the default alphabet is built from |
| `SpokenIdError` and its subclasses | See the errors table above |
| `Excluded` | One character that was left out, and why |

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

Six pairs are still in the alphabet that a careless reader could confuse.
Excluding them costs more characters than it buys, and exclusions have to come
in pairs to keep the count even, so the check character covers them instead.
They are not just a note here — `suggest()` uses them to rank a near miss that
looks like a misreading above one that does not:

```python
sorted("".join(sorted(pair)) for pair in SPOKEN.similar)
# ['0D', '0Q', '49', '56', '7T', 'VW']
```

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
uv run pytest
uv run mypy
uv run ruff check .
```

`pytest` also checks this page against the code: every `python` block is run in
order, every value shown as a `# comment` is compared, every `$ spokenid` block
is executed, and the figures written into the prose above — the alphabet size,
the swap-detection rate, the one-in-forty, the ten collisions — are each
recomputed in `tests/test_readme_figures.py` and required to still say what they
say. Values that change from run to run are marked `# e.g.` and are illustration
rather than a claim.

Changes are listed in [CHANGELOG.md](CHANGELOG.md). Contributions are welcome —
see [CONTRIBUTING.md](CONTRIBUTING.md).

## Licence

Apache-2.0. See [LICENSE](LICENSE).
