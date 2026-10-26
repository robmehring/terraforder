"""Split HCL source into top-level items, keeping each item's text verbatim."""

from __future__ import annotations

import re
from dataclasses import dataclass

_IDENT = re.compile(r"[A-Za-z_][\w-]*")
_HEREDOC = re.compile(r"<<-?([A-Za-z_][\w-]*)[ \t]*\n")
_OPENERS_FOR = {"}": ("{", "${"), "]": ("[",), ")": ("(",)}


class ParseError(Exception):
    def __init__(self, message: str, text: str, pos: int):
        self.line = text.count("\n", 0, pos) + 1
        self.col = pos - (text.rfind("\n", 0, pos) + 1) + 1
        self.message = message
        super().__init__(f"{self.line}:{self.col}: {message}")


@dataclass
class Item:
    kind: str  # "block" or "attribute"
    type: str  # block type, or attribute name
    labels: tuple[str, ...]
    text: str  # leading comments + code, always ends with "\n"

    @property
    def address(self) -> str:
        return ".".join((self.type, *self.labels))


@dataclass
class Document:
    header: str
    items: list[Item]
    footer: str


def parse(text: str) -> Document:
    """Parse source that uses "\\n" line endings."""
    header = ""
    items: list[Item] = []
    pending: list[str] = []
    pos, n = 0, len(text)

    while pos < n:
        line_end = _line_end(text, pos)
        stripped = text[pos:line_end].strip()
        if not stripped or stripped.startswith(("#", "//")):
            pending.append(text[pos:line_end])
            pos = line_end
            continue
        if stripped.startswith("/*"):
            start = text.index("/*", pos)
            close = text.find("*/", start + 2)
            if close == -1:
                raise ParseError("unterminated block comment", text, start)
            end = _line_end(text, close + 2)
            if not text[close + 2 : end].strip():
                pending.append(text[pos:end])
                pos = end
                continue

        end = _scan_item(text, pos)
        detached, attached = _split_lead(pending)
        pending = []
        if items:
            lead = _trim_blank(detached)
            if lead:
                lead += "\n"
        else:
            header = _trim_blank(detached)
            lead = ""
        lead += "".join(attached)
        code = text[pos:end]
        if not code.endswith("\n"):
            code += "\n"
        items.append(_make_item(lead, code, text, pos))
        pos = end

    return Document(header, items, _trim_blank(pending))


def _line_end(text: str, pos: int) -> int:
    j = text.find("\n", pos)
    return len(text) if j == -1 else j + 1


def _split_lead(pending: list[str]) -> tuple[list[str], list[str]]:
    """Split off the comment lines directly above an item (no blank line between)."""
    i = len(pending)
    while i and pending[i - 1].strip():
        i -= 1
    return pending[:i], pending[i:]


def _trim_blank(lines: list[str]) -> str:
    start, end = 0, len(lines)
    while start < end and not lines[start].strip():
        start += 1
    while end > start and not lines[end - 1].strip():
        end -= 1
    joined = "".join(lines[start:end])
    if joined and not joined.endswith("\n"):
        joined += "\n"
    return joined


def _scan_item(text: str, pos: int) -> int:
    """Return the index just past the newline that ends the item starting at pos."""
    n = len(text)
    stack: list[str] = []
    i = pos
    while i < n:
        c = text[i]
        if stack and stack[-1] == '"':
            if c == "\\":
                i += 2
            elif c == '"':
                stack.pop()
                i += 1
            elif c in "$%" and text.startswith(c + "{", i + 1):
                i += 3  # "$${" / "%%{" are literal escapes
            elif c in "$%" and text.startswith("{", i + 1):
                stack.append("${")
                i += 2
            elif c == "\n":
                raise ParseError("unterminated string", text, i)
            else:
                i += 1
            continue

        if c == '"':
            stack.append('"')
            i += 1
        elif c == "#" or text.startswith("//", i):
            nl = text.find("\n", i)
            i = n if nl == -1 else nl
        elif text.startswith("/*", i):
            close = text.find("*/", i + 2)
            if close == -1:
                raise ParseError("unterminated block comment", text, i)
            i = close + 2
        elif text.startswith("<<", i) and (m := _HEREDOC.match(text, i)):
            i = _heredoc_end(text, m.end(), m.group(1), i)
        elif c in "{[(":
            stack.append(c)
            i += 1
        elif c in "}])":
            if not stack or stack[-1] not in _OPENERS_FOR[c]:
                raise ParseError(f"unexpected '{c}'", text, i)
            stack.pop()
            i += 1
        elif c == "\n" and not stack:
            return i + 1
        else:
            i += 1

    if stack:
        raise ParseError(f"unclosed '{stack[-1]}'", text, pos)
    return n


def _heredoc_end(text: str, body_start: int, marker: str, opener: int) -> int:
    """Return the index of the newline after the heredoc's closing marker."""
    j = body_start
    while j < len(text):
        k = _line_end(text, j)
        if text[j:k].strip() == marker:
            return k - 1 if text[k - 1] == "\n" else k
        j = k
    raise ParseError(f"unterminated heredoc '{marker}'", text, opener)


def _skip_trivia(code: str, i: int) -> int:
    while i < len(code):
        if code[i].isspace():
            i += 1
        elif code[i] == "#" or code.startswith("//", i):
            i = _line_end(code, i)
        elif code.startswith("/*", i):
            i = code.index("*/", i) + 2
        else:
            break
    return i


def _make_item(lead: str, code: str, text: str, pos: int) -> Item:
    i = _skip_trivia(code, 0)
    m = _IDENT.match(code, i)
    if not m:
        raise ParseError("expected a block or attribute", text, pos + i)
    name = m.group()
    i = m.end()

    while code[i] in " \t":
        i += 1
    if code.startswith("=", i) and not code.startswith("==", i):
        return Item("attribute", name, (), lead + code)

    labels: list[str] = []
    while True:
        while code[i] in " \t":
            i += 1
        if code[i] == "{":
            return Item("block", name, tuple(labels), lead + code)
        if code[i] == '"':
            j = i + 1
            while j >= len(code) or code[j] != '"':
                if j >= len(code) or code[j] == "\n":
                    raise ParseError("unterminated block label", text, pos + i)
                j += 2 if code[j] == "\\" else 1
            labels.append(code[i + 1 : j])
            i = j + 1
            continue
        m = _IDENT.match(code, i)
        if not m:
            raise ParseError(f"unexpected token in '{name}' block header", text, pos + i)
        labels.append(m.group())
        i = m.end()
