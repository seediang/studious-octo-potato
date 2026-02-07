"""Command-line interface for xbt."""

import argparse
import sys

from . import __version__


def main() -> None:
    """Entry point for the xbt CLI."""
    parser = argparse.ArgumentParser(
        prog="xbt",
        description="xbt - A Python CLI tool",
    )

    parser.add_argument(
        "--version",
        action="version",
        version=f"xbt {__version__}",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Example subcommand
    hello_parser = subparsers.add_parser("hello", help="Greet someone")
    hello_parser.add_argument("name", nargs="?", default="World", help="Name to greet")

    args = parser.parse_args()

    if args.command == "hello":
        print(f"Hello, {args.name}!")
    elif args.command is None:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
