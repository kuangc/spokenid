"""Command line access to the same things the library does.

Run ``spokenid --help`` after installing, or ``python -m spokenid``.
"""

from __future__ import annotations

import argparse
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


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command line. Returns the exit status."""
    args = _build_parser().parse_args(argv)

    try:
        if args.command == "new":
            if args.count < 1:
                print("--count must be at least 1", file=sys.stderr)
                return 1
            scheme = _scheme(args)
            for _ in range(args.count):
                identifier = scheme.random()
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
