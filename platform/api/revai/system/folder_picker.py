"""Native directory selection for the local desktop workflow."""

from __future__ import annotations

from pathlib import Path
from typing import Any


class FolderPickerError(RuntimeError):
    """The native directory dialog could not be opened.

    Carries a namespaced ``error_key`` and structured ``params`` for the
    API's error contract.
    """

    def __init__(self, error_key: str, params: dict[str, Any] | None = None) -> None:
        self.error_key = error_key
        self.params = params or {}
        super().__init__(error_key)


def pick_directory() -> Path | None:
    """Open the operating system's folder picker.

    Browsers do not expose absolute directory paths. RevAI is loopback-only, so
    the local API can safely open a native dialog and return the selected path.
    """
    try:
        import tkinter as tk
        from tkinter import filedialog
    except ImportError as exc:
        raise FolderPickerError("folder_picker.tk_not_installed") from exc

    root: tk.Tk | None = None
    try:
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        selected = filedialog.askdirectory(
            parent=root,
            title="Select a folder",
            mustexist=True,
        )
    except tk.TclError as exc:
        raise FolderPickerError("folder_picker.unavailable_in_session") from exc
    finally:
        if root is not None:
            root.destroy()

    return Path(selected).resolve() if selected else None
