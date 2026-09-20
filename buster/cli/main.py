"""Main entry point for the Buster CLI."""

import sys


def main(argv: list[str] | None = None) -> int:
    from buster.cli.commands import dispatch_command

    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        argv = ["help"]

    command = argv[0]
    args = argv[1:]
    return dispatch_command(command, args)


if __name__ == "__main__":
    sys.exit(main())