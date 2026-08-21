# spokenid — design

**Date:** 2026-08-17
**Status:** approved

## What it is

A Python library that issues short identifiers people can read aloud over a
phone, write on a paper form, and type back without ambiguity.

## Why

Antara Health ran an identifier scheme like this for six years. The good idea in
it was a character set with no vowels, so an identifier can never spell a word in
any language. Nothing published does that: Crockford Base32 drops one vowel and
its stated test is George Carlin's list of seven English words, and OpenMRS keeps
A, E and U.

Two things Antara got wrong, both fixed here:

1. It removed the digits `0` and `1` as well as the letters `O` and `I`. Removing
   both halves of a confusable pair means a mistyped `O` can no longer be resolved
   to anything. Keep the digit, drop the letter, and the repair is deterministic.
2. Its alphabet had 27 characters. Luhn mod N only detects every single-character
   error in an even base, so a check digit over 27 characters misses about 1 error
   in 40. The same defect exists today in OpenMRS `LuhnMod25IdentifierValidator`.

## The alphabet

    0123456789CDFHJKMNPQRTVWXY      26 characters

Derived from rules, not hand-typed:

- Drop `A E I O U`. No vowels means no words, in any language, without a blocklist.
- For each remaining lookalike pair, drop the letter and keep the digit:
  `B→8  G→6  I→1  L→1  O→0  S→5  Z→2`

Properties:

- No vowels.
- Every dropped confusable maps to exactly one kept character, so repair is total.
- 26 characters, an even count, so the Luhn check digit detects every
  single-character error. Verified by exhaustive enumeration.
- A strict subset of Crockford Base32, so every identifier is also a valid
  Crockford string.

Six weaker pairs remain in the set: `0/Q 0/D 7/T V/W 4/9 5/6`. Excluding them
costs more characters than it buys, and the check digit is the backstop.

## Public API

One class.

```python
Scheme(alphabet=SPOKEN, length=8, groups=(4, 4), separator="-", check=True)
```

| Method | Purpose |
| --- | --- |
| `random(taken=None, attempts=10)` | Draw a new identifier. Retry while `taken(id)`. |
| `next(previous, step=1)` | The successor of `previous`. Cannot collide. |
| `first()` | The first identifier of a sequence. |
| `parse(raw)` | Normalise, repair confusables, verify the check digit. |
| `validate(raw)` | `True` if `raw` parses and needs no repair. |
| `describe(members)` | Size of the space and guessability at that population. |
| `space` | Count of possible identifiers. |

`parse` returns a `Parsed` with `ok`, `value`, `repairs` and `problem`. Repairs are
reported, never applied silently: rewriting a patient identifier without saying so
is how the wrong record gets opened.

## Two ways to issue

**Random** suits anything reachable over a network. Needs a uniqueness check,
supplied by the caller as a function so the library never knows about a database.
Raises `SpaceExhausted` after `attempts` collisions rather than looping, with a
message naming the cause.

**Sequential** suits a clinic with a paper register: gaps are visible, cards file
in order, and no lookup is needed. `next()` treats the body as a base-26 number,
adds `step`, and recomputes the check digit. It cannot collide by construction.
Identifiers sort lexicographically in issue order, because the alphabet is in
ascending order and the body is fixed width. Sequential identifiers are guessable;
`step` accepts any integer, so `scheme.next(prev, step=random.randint(1, 50))`
buys gaps without losing the ordering or the guarantee.

## Errors

`SpokenIdError` is the base. `SpaceExhausted` when random drawing keeps colliding.
`SequenceExhausted` when `next()` runs past the last identifier. `InvalidScheme`
when a `Scheme` is impossible to construct, including an odd alphabet with the
check digit on.

## Deliberately excluded

- Encoding arbitrary numbers. Use Crockford Base32.
- Damm's algorithm. Odd alphabets are refused with an explanation instead;
  turn the check digit off to use one.
- Any database, ORM or service integration. `taken` is a function.
- A blocklist of rude words. The alphabet is the mechanism that replaces it.

## Quality bar

Judged the way a stranger judges a package: working example in the first screen of
the README, no runtime dependencies, type hints with `py.typed`, tests in CI on
every supported Python version, lint and type checks in CI, a licence, a changelog,
and an honest statement of when not to use it.
