"""Native directory selection for the local desktop workflow."""

from __future__ import annotations

from pathlib import Path


class FolderPickerError(RuntimeError):
    """The native directory dialog could not be opened."""


def pick_directory() -> Path | None:
    """Open the operating system's folder picker.

    Browsers do not expose absolute directory paths. RevAI is loopback-only, so
    the local API can safely open a native dialog and return the selected path.
    """
    try:
        import tkinter as tk
        from tkinter import filedialog
    except ImportError as exc:
        raise FolderPickerError(
            "Native folder selection is unavailable because Tk is not installed."
        ) from exc

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
        raise FolderPickerError(
            "Native folder selection is unavailable in this desktop session."
        ) from exc
    finally:
        if root is not None:
            root.destroy()

    return Path(selected).resolve() if selected else None
