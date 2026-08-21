# Security

## Reporting a vulnerability

Please report security issues through
[GitHub's private advisory form](https://github.com/kuangc/spokenid/security/advisories/new)
rather than a public issue. You should get a reply within a week.

## What this library is not

An identifier is not a credential, and this library does not pretend otherwise.

- **Identifiers are not secrets.** `random()` draws from `secrets`, so an
  identifier is unpredictable, but anyone who sees one can repeat it.
  Authentication is what keeps a record private.
- **Counted identifiers are guessable by design.** `next()` returns the
  successor, so holding one identifier means holding the next. Use `random()`
  where an identifier appears in a URL, or pass a random `step`.
- **Length is your decision.** `Scheme.describe()` reports how often a blind
  guess names a real member at a given population. Check it before choosing.
- **The check character catches mistakes, not tampering.** It is an error
  detector, not a signature, and anyone can compute it.
