# Contributing

Thanks for looking. Bug reports and pull requests are both welcome.

## Getting set up

```bash
git clone https://github.com/kuangc/spokenid
cd spokenid
uv sync
```

## Before you open a pull request

```bash
uv run pytest          # tests, doctests, and the README examples
uv run mypy            # strict, and it has to stay clean
uv run ruff check .
uv run ruff format .
```

CI runs all of these on Python 3.10 through 3.14.

## What this project is trying to be

Small, and honest about what it does not do. Two things follow from that:

**New behaviour needs a reason someone would miss it.** The
[README](README.md#when-not-to-use-this) lists what is deliberately absent. If
you want to add something on that list, the discussion is about moving it off
the list first.

**A promise in the README needs a test that proves it.** The claims about vowels,
repairs, check characters and ordering are all covered in
`tests/test_properties.py`, where Hypothesis tries to break them. Assertions in
prose are not enough.

If you change an alphabet, note that the check character only catches every
single-character mistake when the alphabet has an even number of characters.
`tests/test_check.py` proves this exhaustively, and `Luhn` refuses to be built
over an odd one.

## Reporting a bug

Say what you expected, what happened, and the shortest code that shows it. If
Hypothesis found it for you, include the `@seed(...)` line it printed.

## Releasing

See [RELEASING.md](https://github.com/kuangc/spokenid/blob/main/RELEASING.md).
