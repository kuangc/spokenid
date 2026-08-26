# 1. An alphabet with no vowels and no lookalike pairs

Status: accepted
Date: 2020, recorded 2026-08-25

## Context

Identifiers were read aloud over the phone between members and clinicians in
Kenya, written on paper forms, and typed back. Two things go wrong when people
handle identifiers: the string reads as a word, sometimes an offensive one, and
characters get confused with each other. A list of words to avoid has to be
written once per language and is still incomplete.

## Decision

Drop all five vowels, and for each pair of characters that get confused, drop
one and keep the other. The result is 26 characters:

```
0123456789CDFHJKMNPQRTVWXY
```

Keep the digit and drop the letter, so a misreading resolves to exactly one
answer: `O` was a zero, `S` was a five. Dropping both halves of a pair would
cost two characters and leave a typed `O` meaning nothing.

## Consequences

Removing the vowels removes almost every accidental word, and the whole class
of accidental profanity a vowel-carrying alphabet produces. It is not absolute:
vowel-free words exist in some languages.

Six pairs remain confusable inside the alphabet — `0/Q`, `0/D`, `7/T`, `V/W`,
`4/9`, `5/6`. Excluding them costs more than it buys, and exclusions have to
come in pairs to keep the count even (see [0002](0002-damm-check-character.md)).
The check character covers them. `Alphabet.similar` exposes the list.

26 characters gives 8.03 billion identifiers at seven random symbols.
