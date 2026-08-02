"""Crash-isolated Tree-sitter symbol extraction.

This module is an internal subprocess entry point. Source arrives on stdin and the
only stdout payload is a JSON list of symbol boundaries.
"""

from __future__ import annotations

import json
import sys

_SYMBOL_NODE_TYPES = {
    "class_declaration",
    "class_definition",
    "function_declaration",
    "function_definition",
    "interface_declaration",
    "method_declaration",
    "method_definition",
    "struct_item",
}


def main() -> int:
    if len(sys.argv) != 2:
        return 2

    from tree_sitter_language_pack import get_parser

    source = sys.stdin.buffer.read()
    tree = get_parser(sys.argv[1]).parse(source)
    symbols: list[dict[str, str | int | None]] = []
    stack = [tree.root_node]
    while stack:
        node = stack.pop()
        if node.type in _SYMBOL_NODE_TYPES:
            name_node = node.child_by_field_name("name")
            name = (
                source[name_node.start_byte : name_node.end_byte].decode(
                    "utf-8",
                    errors="replace",
                )
                if name_node is not None
                else None
            )
            symbols.append(
                {
                    "name": name,
                    "line_start": int(node.start_point.row) + 1,
                    "line_end": int(node.end_point.row) + 1,
                }
            )
        stack.extend(node.children)

    sys.stdout.write(json.dumps(symbols, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
