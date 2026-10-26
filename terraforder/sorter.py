from __future__ import annotations

from collections.abc import Sequence

from .parser import Document, Item, parse

DEFAULT_ORDER: tuple[str, ...] = (
    "terraform",
    "provider",
    "variable",
    "locals",
    "data",
    "resource",
    "module",
    "moved",
    "import",
    "removed",
    "check",
    "output",
)


def sort_items(items: Sequence[Item], order: Sequence[str] = DEFAULT_ORDER) -> list[Item]:
    """Attributes first, then blocks grouped by `order` (unknown types last), each alphabetical."""
    rank = {block_type: i for i, block_type in enumerate(order)}

    def key(item: Item):
        group = -1 if item.kind == "attribute" else rank.get(item.type, len(order))
        return (
            group,
            item.type.lower(),
            item.type,
            tuple(label.lower() for label in item.labels),
            item.labels,
        )

    return sorted(items, key=key)


def render(doc: Document, items: Sequence[Item]) -> str:
    out: list[str] = []
    if doc.header:
        out.append(doc.header)
    prev = None
    for item in items:
        if out and not (_is_compact(prev) and _is_compact(item)):
            out.append("\n")
        out.append(item.text)
        prev = item
    if doc.footer:
        out.append("\n" + doc.footer)
    return "".join(out)


def _is_compact(item: Item | None) -> bool:
    return item is not None and item.kind == "attribute" and item.text.count("\n") == 1


def sort_source(text: str, order: Sequence[str] = DEFAULT_ORDER) -> tuple[str, list[Item]]:
    """Return the sorted source (line endings preserved) and the items in their new order."""
    crlf = "\r\n" in text
    doc = parse(text.replace("\r\n", "\n"))
    if not doc.items:
        return text, []
    items = sort_items(doc.items, order)
    result = render(doc, items)
    if crlf:
        result = result.replace("\n", "\r\n")
    return result, items
