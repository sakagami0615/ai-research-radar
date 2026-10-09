"""Escaping of text written into the daily Markdown report.

Titles, summaries and URLs come from external sources and Agent-written files,
so every value goes through one of these functions depending on where it is
placed:

- `span`: text after a prefix on one line (link text, "- 概要: ..." etc.)
- `inline`: one line that may start a list item or paragraph (block markers escaped)
- `heading`: the text of an ATX heading
- `cell`: one table cell (newlines become <br>)
- `paragraph`: a multi-line paragraph of its own (newlines become <br>)
- `url`: a link destination inside `<...>`
"""

from __future__ import annotations

import re

_ORDERED_MARKER = re.compile(r"^(\d+)([.)])(?=\s)")
# Any leading character that can open a block (heading, list, thematic break, code fence,
# setext underline) is escaped; a backslash before ASCII punctuation always renders as-is.
_BLOCK_MARKER = re.compile(r"^([#=+*_`~-])")


def escape_text(text: str) -> str:
    """Backslash-escape `\\`, `[]` and `|`, and turn `<>` into entities (no links, tags or table breaks)."""
    escaped = text.replace("\\", "\\\\")
    escaped = escaped.replace("[", "\\[").replace("]", "\\]").replace("|", "\\|")
    return escaped.replace("<", "&lt;").replace(">", "&gt;")


def span(value: object) -> str:
    """Escaped text on one line; newlines and runs of whitespace collapse to one space.

    Non-strings (hand-edited records) become empty.
    """
    text = value if isinstance(value, str) else ""
    return " ".join(escape_text(text).split())


def inline(value: object) -> str:
    """`span` whose leading block marker is escaped, so it stays plain text at a line start."""
    return _escape_block_marker(span(value))


def heading(value: object) -> str:
    escaped = span(value)
    if escaped.endswith("#"):
        # A trailing "#" would be consumed as the ATX heading's closing sequence.
        escaped = escaped[:-1] + "\\#"
    return escaped


def cell(value: object) -> str:
    """Escape a value for a single table cell; newlines become <br> so they cannot end the row."""
    escaped = escape_text(str(value))
    escaped = escaped.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "<br>")
    return escaped or "-"


def paragraph(value: str) -> str:
    """A multi-line text on its own line: newlines become <br>, the leading block marker is escaped."""
    escaped = escape_text(value.strip())
    escaped = escaped.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "<br>")
    return _escape_block_marker(escaped)


def url(value: str) -> str:
    """Percent-encode a link destination used inside `<...>`.

    `<>` cannot end the destination early, and `\\`, `|` and newlines cannot
    escape it or break a table row. HTML entities are not used because some
    viewers would keep them literally in the URL.
    """
    encoded = value.replace("\\", "%5C").replace("<", "%3C").replace(">", "%3E").replace("|", "%7C")
    return encoded.replace("\r", "%0D").replace("\n", "%0A")


def _escape_block_marker(text: str) -> str:
    text = _ORDERED_MARKER.sub(r"\1\\\2", text, count=1)
    return _BLOCK_MARKER.sub(r"\\\1", text, count=1)
