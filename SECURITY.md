# Security

## Reporting a vulnerability

Please report security issues through
[GitHub's private advisory form](https://github.com/kuangc/spokenid/security/advisories/new)
rather than a public issue. You should get a reply within a week.

## What this library is not

An identifier is not a credential, and this library does not pretend otherwise.

- **Identifiers are not secrets.** `random()` uses a cryptographically strong
  generator and does not encode issue order, but guess resistance still depends on
  length and population. Anyone who sees an identifier can repeat it. Authentication
  and authorization are what keep a record private.
- **Counted identifiers are enumerable by design.** `first()` and `next()` map
  positions to stable values. Do not rely on gaps to hide the sequence; counted values
  still reveal issue order. Use `random()` when identifiers should not reveal issue
  order, including when an identifier appears in a URL.
- **Length is your decision.** `Scheme.describe()` reports uniform full-space guess
  odds without allocation knowledge. That is not the attacker model for a counted
  sequence. Check it before choosing.
- **The check character catches mistakes, not tampering.** It is an error
  detector, not a signature, and anyone can compute it.
