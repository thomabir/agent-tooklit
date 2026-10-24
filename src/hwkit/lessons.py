"""Lessons file: general design principles, one top-level bullet ("- ") per entry, at most MAX_ENTRIES."""

MAX_ENTRIES = 100


def entries(text):
    return [line for line in text.splitlines() if line.startswith("- ")]


def check(path):
    """Returns (lines, issues)."""
    n = len(entries(path.read_text()))
    lines = [f"lessons: {n} of {MAX_ENTRIES} entries"]
    return lines, ([f"{path}: {n} entries > {MAX_ENTRIES}; compress (merge, abstract, or move entries to the archive)"] if n > MAX_ENTRIES else [])
