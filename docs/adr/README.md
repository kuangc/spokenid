# Architecture decision records

Short notes on decisions that would otherwise have to be rediscovered from the
code. One decision per file, numbered, newest last. A record is not rewritten
when a decision changes; a later record supersedes it and says so.

The format is [MADR](https://adr.github.io/madr/) trimmed to what a small
library needs: context, the decision, and what it costs.

| # | Decision |
|---|---|
| [0001](0001-vowel-free-alphabet.md) | An alphabet with no vowels and no lookalike pairs |
| [0002](0002-damm-check-character.md) | Damm rather than Luhn as the default check character |
| [0003](0003-repairs-are-reported.md) | Repairs are reported, never applied silently |
| [0004](0004-no-storage-in-the-library.md) | The library owns no storage and no allocator |
| [0005](0005-guarantees-separate-from-evaluation.md) | Exact guarantees kept separate from synthetic evaluation |
