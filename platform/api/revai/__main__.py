"""Entry point so the API can be started with ``python -m revai``."""

from __future__ import annotations

from pathlib import Path

import uvicorn

from revai.config import get_settings

# The package directory. Scoping the reloader to this avoids watching the whole
# repository, which would otherwise restart the server on unrelated edits.
PACKAGE_DIR = Path(__file__).resolve().parent


def main() -> None:
    settings = get_settings()
    reload = settings.environment == "development"
    uvicorn.run(
        "revai.main:app",
        host=settings.host,
        port=settings.port,
        reload=reload,
        reload_dirs=[str(PACKAGE_DIR)] if reload else None,
        log_level="info",
    )


if __name__ == "__main__":
    main()
