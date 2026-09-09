# Contributing

Thanks for looking. Bug reports and pull requests are both welcome.

## Getting set up

```bash
git clone https://github.com/kuangc/spokenid
cd spokenid
uv sync --locked
```

## Before you open a pull request

```bash
uv run --locked pytest          # tests, doctests, and the README examples
uv run --locked mypy            # strict, and it has to stay clean
uv run --locked ruff check .
uv run --locked ruff format --check .
```

CI runs pytest on Python 3.10 through 3.14; mypy and Ruff run once.

## What this project is trying to be

Small, and honest about what it does not do. Two things follow from that:

**New behaviour needs a reason someone would miss it.** The
[README](README.md#when-not-to-use-this) lists what is deliberately absent. If
you want to add something on that list, the discussion is about moving it off
the list first.

**A promise in the README needs a test that proves it.** General invariants live in
`tests/test_properties.py`; the default `Damm` table and guarantees are exercised in
`tests/test_damm.py`; and the explicit `Luhn` fallback is covered in
`tests/test_check.py`. Assertions in prose are not enough.

Any 26-character alphabet with `check=True` uses `Damm`; other supported even sizes
use `Luhn`; an odd-sized `Luhn` fallback is refused. Changes to those contracts also
belong in the deterministic `benchmarks/evaluate.py` model and its
`tests/test_evaluation.py` tests.

## Reporting a bug

Say what you expected, what happened, and the shortest code that shows it. If
Hypothesis found it for you, include the `@seed(...)` line it printed.

## Design decisions

Decisions that would otherwise have to be rediscovered from the code are
recorded in [docs/adr](https://github.com/kuangc/spokenid/blob/main/docs/adr).
Add one when a change turns on a judgement call rather than on a fact; leave the
existing records alone and supersede them with a new one.

## Releasing

See [RELEASING.md](https://github.com/kuangc/spokenid/blob/main/RELEASING.md).
