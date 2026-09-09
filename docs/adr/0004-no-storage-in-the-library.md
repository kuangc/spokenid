# 4. The library owns no storage and no allocator

Status: accepted
Date: 2026-08-24

## Context

Issuing identifiers looks like it needs state: something has to know which
values are taken, or how far a sequence has advanced. The obvious designs are a
service that owns allocation, or a library that talks to a database.

Both make the library responsible for a guarantee it cannot keep. Uniqueness is
enforced by a unique index, and serialization by a transaction; a library that
appears to own either invites callers to skip both.

## Decision

`random(taken=...)` takes a predicate supplied by the caller. `next(previous)`
is stateless: the caller persists and advances sequence state in the same
transaction as the record insert. The library holds no database handle, no
allocator, and no hidden mutable state.

## Consequences

The integration surface is one function. Nothing in the library needs to know
about a database, so nothing about a database can be wrong in it.

`random(taken=...)` is collision filtering for a single serialized writer, not
an atomic guarantee. Two writers can still draw the same value, and the unique
index is what stops it. Without `taken` it draws once and can return a value
already issued.

`next()` assumes one writer for the same reason.
