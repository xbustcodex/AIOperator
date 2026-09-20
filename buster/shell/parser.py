"""Command parser for the interactive shell.

Tokenizes input respecting single and double quotes (including attached
``key="value"`` assignments), and splits off ``--flag`` options. Result is
a ``Command`` with name, positional args and options.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Command:
    name: str
    args: list[str] = field(default_factory=list)
    options: dict = field(default_factory=dict)

    def option(self, key: str, default=None):
        return self.options.get(key, default)


def tokenize(line: str) -> list[str]:
    """Split a line into tokens, keeping quoted whitespace intact."""
    tokens: list[str] = []
    buffer: list[str] = []
    quote: Optional[str] = None
    i, n = 0, len(line)
    while i < n:
        ch = line[i]
        if quote is not None:
            buffer.append(ch)
            if ch == quote:
                quote = None
            i += 1
            continue
        if ch in "\"'":
            quote = ch
            buffer.append(ch)
            i += 1
            continue
        if ch.isspace():
            if buffer:
                tokens.append("".join(buffer))
                buffer = []
            i += 1
            continue
        buffer.append(ch)
        i += 1
    if buffer:
        tokens.append("".join(buffer))
    return tokens


def strip_outer_quotes(token: str) -> str:
    if len(token) >= 2 and token[0] in "\"'" and token[-1] == token[0]:
        return token[1:-1]
    for quote_char in ("\"", "'"):
        if quote_char in token:
            key, eq, rest = token.partition("=")
            if eq and rest.startswith(quote_char) and rest.endswith(quote_char):
                return f"{key}={rest[1:-1]}"
    return token


def parse(line: str) -> Optional[Command]:
    """Parse a single command line into a Command (None for empty lines)."""
    line = line.strip()
    if not line:
        return None

    tokens = [strip_outer_quotes(t) for t in tokenize(line)]
    if not tokens:
        return None

    name = tokens[0]
    args: list[str] = []
    options: dict = {}
    i = 1
    while i < len(tokens):
        token = tokens[i]
        if token.startswith("--") and "=" in token:
            key, _, value = token[2:].partition("=")
            options[key] = coerce(value)
            i += 1
            continue
        if token.startswith("--"):
            key = token[2:]
            if i + 1 < len(tokens) and not tokens[i + 1].startswith("--"):
                options[key] = coerce(tokens[i + 1])
                i += 2
            else:
                options[key] = True
                i += 1
            continue
        if token.startswith("-") and len(token) == 2:
            options[token[1]] = True
            i += 1
            continue
        args.append(token)
        i += 1

    return Command(name=name, args=args, options=options)


def coerce(value: str):
    """Coerce option values to int/float/bool where obvious, else str."""
    lowered = value.lower()
    if lowered in ("true", "false"):
        return lowered == "true"
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        pass
    return value