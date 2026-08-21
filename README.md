# spokenid

Short identifiers that people can say out loud, write on a form, and type back
correctly. No vowels, so an identifier can never spell a word in any language.
No character that looks like another one in the set.

```
4KM7-PC2M
```

No dependencies. Type hints throughout. Python 3.10 and up.

```bash
pip install spokenid
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

read.ok  # True
read.value  # '7HW2-0J46'   what they meant
read.repairs  # what had to be reinterpreted, so you can confirm it
```

And when it is genuinely wrong, you get a sentence you can show them:

```python
scheme.parse("7HW2-0J4X").problem
# 'this is not a valid identifier; check it for a typing mistake'
```

That is the whole idea. The rest of this page is detail.

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

SPOKEN.explain("A")
# "'A' was dropped because it is a vowel, and there is no other character it could be mistaken for"
```

## Two ways to issue an identifier

### Random, when it might appear in a URL

You supply the uniqueness check, so this library never needs to know about your
database.

```python
issued = set()

scheme.random(taken=lambda candidate: candidate in issued)
```

After ten collisions in a row it raises `SpaceExhausted` rather than looping
forever, and the message tells you the population has outgrown the scheme.

### Counting, when it must never collide

Give it the last identifier you issued and it hands back the next one. No lookup,
no collision, by construction.

```python
scheme.first()
# '0000-0000'

scheme.next("0000-0000")
# '0000-001X'
```

Counted identifiers also sort into the order they were issued, which is useful
when they are filed on paper.

Counted identifiers are guessable, though. If that matters, leave gaps. The
ordering and the no-collision guarantee both survive:

```python
import random

scheme.next("0000-001X", step=random.randint(1, 50))
```

## Choosing the length

```python
print(Scheme(length=8, groups=(4, 4)).describe())
```

```
26^7 = 8,031,810,176 identifiers (8 characters, shown as XXXX-XXXX)
  at     10,000 members, a blind guess names a real one 1 in 803,181
  at    100,000 members, a blind guess names a real one 1 in 80,318
  at  1,000,000 members, a blind guess names a real one 1 in 8,032
```

The last column is the number to choose by. A repeat drawn at random is not a
failure, because `random()` simply draws again and nobody sees it. An identifier
that is easy to guess is a way to reach someone else's record.

Note that the check character uses one of your characters, so an eight-character
identifier carries seven random ones.

## The last character catches mistakes

Like the last digit of a credit card number. It catches **every** single-character
mistake, and most swaps of neighbouring characters.

That guarantee needs an alphabet with an even number of characters, which is why
this one has twenty-six. An odd alphabet lets roughly one mistake in forty through
unnoticed, so `Scheme` refuses to build one rather than quietly promising less
than it delivers:

```python
from spokenid import Alphabet, Scheme, InvalidScheme

odd = Alphabet.derive(lookalikes={"I": "1", "O": "0", "B": "8", "S": "5"})
len(odd)  # 29

try:
    Scheme(alphabet=odd)
except InvalidScheme as error:
    print(error)
# a Luhn check character only catches every single-character mistake when the
# alphabet has an even number of characters; this one has 29. ...
```

Turn it off with `Scheme(check=False)` if you would rather have the extra
character, and any odd alphabet then works.

## Reading it out loud

```python
from spokenid import phonetic

phonetic("4KM7-PC2M")
# '4 Kilo Mike 7, Papa Charlie 2 Mike'
```

## When not to use this

- **You need to encode a number.** These identifiers are drawn, not encoded. Use
  [Crockford Base32](https://www.crockford.com/base32.html), which this alphabet
  is a subset of.
- **Nobody ever types or says the identifier.** Then it should be a UUID, and the
  constraints here cost you entropy for nothing.
- **You need a secret.** An identifier is not a credential. Guessing resistance is
  a bonus; authentication is the thing that keeps records private.
- **You need every neighbour swap caught.** The check character catches most, not
  all. Damm's algorithm catches all and is not implemented here.

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
validator uses an odd alphabet.

## Development

```bash
uv sync
uv run pytest
uv run mypy
uv run ruff check .
```

## Licence

Apache-2.0. See [LICENSE](LICENSE).
