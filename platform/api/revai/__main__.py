"""Backward-compatible API entry point for ``python -m revai``."""

from __future__ import annotations

from revai.cli import serve_api


def main() -> None:
    serve_api()


if __name__ == "__main__":
    main()
