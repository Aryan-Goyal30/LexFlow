"""Formatting shared by the API responses."""

from __future__ import annotations


def format_file_size(size_bytes: int) -> str:
    """Same rule as the front end's ``formatFileSize``: B, whole KB, or MB to 1 dp."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024 * 1024:
        return f"{round(size_bytes / 1024)} KB"
    return f"{size_bytes / (1024 * 1024):.1f} MB"
