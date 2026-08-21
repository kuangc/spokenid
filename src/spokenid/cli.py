"""Command line access to the same things the library does.

Run ``spokenid --help`` after installing, or ``python -m spokenid``.
"""

from __future__ import annotations

import argparse
import contextlib
import errno
import os
import sys
from collections.abc import Sequence

from . import __version__
from .alphabet import SPOKEN
from .errors import SpokenIdError
from .phonetic import phonetic
from .scheme import Scheme

__all__ = ["main"]


def _scheme(args: argparse.Namespace) -> Scheme:
    return Scheme(length=args.length, check=not args.no_check)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="spokenid",
        description="Identifiers people can say out loud and type back correctly.",
    )
    parser.add_argument("--version", action="version", version=f"spokenid {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    def shared(p: argparse.ArgumentParser) -> None:
        p.add_argument(
            "--length", type=int, default=8, help="characters per identifier (default 8)"
        )
        p.add_argument(
            "--no-check",
            action="store_true",
            help="leave off the character that catches mistakes",
        )

    new = sub.add_parser("new", help="make one or more identifiers")
    shared(new)
    new.add_argument("-n", "--count", type=int, default=1, help="how many (default 1)")
    new.add_argument(
        "--plain", action="store_true", help="no separator, for piping elsewhere"
    )

    check = sub.add_parser("check", help="read an identifier and say whether it is valid")
    shared(check)
    check.add_argument("identifier")

    nxt = sub.add_parser("next", help="the identifier after this one")
    shared(nxt)
    nxt.add_argument("identifier")
    nxt.add_argument("--step", type=int, default=1, help="how far to advance (default 1)")

    say = sub.add_parser("say", help="spell an identifier for reading aloud")
    say.add_argument("identifier")

    describe = sub.add_parser("describe", help="how big a scheme is, and how guessable")
    shared(describe)
    describe.add_argument(
        "--members", type=int, default=100_000, help="population to report for"
    )

    sub.add_parser("alphabet", help="show the alphabet and why each character is in it")
    return parser


#: Errors a write raises when the far end of a pipe has gone. Windows reports
#: EINVAL rather than the BrokenPipeError POSIX gives, so both are handled.
_PIPE_GONE = frozenset({errno.EPIPE, errno.EINVAL, errno.ESHUTDOWN})


def _is_closed_pipe(error: OSError) -> bool:
    return isinstance(error, BrokenPipeError) or error.errno in _PIPE_GONE


def _abandon_output() -> None:
    """Point both streams at nothing, so the exit flush cannot raise again."""
    with contextlib.suppress(OSError, ValueError):
        devnull = os.open(os.devnull, os.O_WRONLY)
        for stream in (sys.stdout, sys.stderr):
            with contextlib.suppress(OSError, ValueError):
                os.dup2(devnull, stream.fileno())


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command line. Returns the exit status.

    Wraps :func:`_run` so a closed pipe is quiet. The flush has to happen here
    rather than being left to the interpreter: anything shorter than the 8 KB
    buffer is still unwritten when the command body returns, so the failure
    would otherwise land outside every handler and exit 120 with a traceback.

    Returns 141, the shell's convention for a command killed by SIGPIPE, on
    every platform. Windows has no such signal, but a single answer is easier
    to script against than two.
    """
    try:
        status = _run(argv)
        sys.stdout.flush()
        sys.stderr.flush()
    except OSError as error:
        if not _is_closed_pipe(error):
            raise
        _abandon_output()
        return 141
    except SystemExit:
        # argparse exits this way for --help, --version and bad arguments,
        # and its output is unflushed at this point too.
        try:
            sys.stdout.flush()
            sys.stderr.flush()
        except OSError as error:
            if not _is_closed_pipe(error):
                raise
            _abandon_output()
            return 141
        raise
    return status


def _run(argv: Sequence[str] | None = None) -> int:
    """Do the work. See :func:`main`, which handles a closed pipe."""
    args = _build_parser().parse_args(argv)

    try:
        if args.command == "new":
            if args.count < 1:
                print("--count must be at least 1", file=sys.stderr)
                return 1
            scheme = _scheme(args)
            # random() draws once; without a uniqueness check it can repeat.
            # A batch printed by one command should not contain a duplicate.
            issued: set[str] = set()
            for _ in range(args.count):
                identifier = scheme.random(taken=issued.__contains__)
                issued.add(identifier)
                print(
                    identifier.replace(scheme.separator, "") if args.plain else identifier
                )
            return 0

        if args.command == "check":
            scheme = _scheme(args)
            read = scheme.parse(args.identifier)
            if not read.ok:
                print(read.problem, file=sys.stderr)
                for candidate in scheme.suggest(args.identifier):
                    print(f"  did you mean {candidate}?", file=sys.stderr)
                return 1
            print(read.value)
            for repair in read.repairs:
                print(f"  {repair}", file=sys.stderr)
            return 0

        if args.command == "next":
            print(_scheme(args).next(args.identifier, step=args.step))
            return 0

        if args.command == "say":
            print(phonetic(args.identifier))
            return 0

        if args.command == "describe":
            print(_scheme(args).describe([args.members]))
            return 0

        if args.command == "alphabet":
            print(SPOKEN.characters)
            print(f"{len(SPOKEN)} characters, no vowels")
            for item in SPOKEN.excluded:
                print(f"  {SPOKEN.explain(item.char)}")
            return 0

    except SpokenIdError as error:
        print(error, file=sys.stderr)
        return 1

    return 1  # pragma: no cover - argparse rejects unknown commands first


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
