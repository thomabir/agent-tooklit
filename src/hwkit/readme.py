"""Project README: section check and generated blocks.

Each section holds content, "TODO", or "N/A: <reason>". Guidance text is in HTML comments, which do not count as content.
Generated blocks are between "<!-- BEGIN generated: <name> -->" and "<!-- END generated: <name> -->".
"""

import re

# Required sections as (level 2 heading, level 3 heading or None), in template order.
SECTIONS = (
    ("Status and errata", None),
    ("Function", None),
    ("Design", None),
    ("Design", "Specifications"),
    ("Bill of materials", None),
    ("Interfaces", None),
    ("Interfaces", "Mechanical"),
    ("Interfaces", "Electrical"),
    ("Interfaces", "User interface"),
    ("Interfaces", "Other"),
    ("Build", None),
    ("Build", "PCB"),
    ("Build", "Assembly"),
    ("Build", "Case"),
    ("Build", "Bring-up and programming"),
    ("Build", "Test procedure"),
    ("Systems engineering", None),
    ("Systems engineering", "Power"),
    ("Systems engineering", "Signal and noise"),
    ("Systems engineering", "Safety"),
    ("Systems engineering", "Other"),
    ("Licence", None),
)

_HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*$")
_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
_BLOCK = re.compile(r"(<!-- BEGIN generated: ([\w-]+) -->\n)(.*?)(<!-- END generated: \2 -->)", re.DOTALL)


def title(text):
    """Text of the first level 1 heading, or None."""
    for line in _COMMENT.sub("", text).splitlines():
        m = _HEADING.match(line)
        if m and len(m.group(1)) == 1:
            return m.group(2)
    return None


def sections(text):
    """{(h2, h3 or None): (body, has subsections)}. body: text up to the next heading, without HTML comments. Generated blocks count as content."""
    found, h2, path, body = {}, None, None, []
    lines = _COMMENT.sub(lambda m: "GENERATED" if m.group(0).startswith("<!-- BEGIN generated:") else "", text).splitlines()

    def close(next_level):
        if path is not None:
            found[path] = ("\n".join(body).strip(), next_level == 3 and path[1] is None)

    for line in lines:
        m = _HEADING.match(line)
        if not m or len(m.group(1)) == 1:
            body.append(line)
            continue
        level = len(m.group(1))
        if level > 3:
            body.append(line)
            continue
        close(level)
        if level == 2:
            h2 = m.group(2)
            path = (h2, None)
        else:
            path = (h2, m.group(2))
        body = []
    close(None)
    return found


def state(body, has_subsections):
    """'todo', 'na', 'content', 'empty' (no body, but subsections), or 'missing content'."""
    lines = [line.strip() for line in body.splitlines()]
    if "TODO" in lines:
        return "todo"
    if lines and lines[0].startswith("N/A:") and lines[0][4:].strip():
        return "na"
    if any(lines):
        return "content"
    return "empty" if has_subsections else "missing content"


def check(text, release=False, expected_title=None):
    """Returns (lines, issues). release: TODO is an issue, else a note."""
    lines, issues = [], []
    found = sections(text)
    t = title(text)
    if t is None:
        issues.append("README: no level 1 heading")
    elif expected_title is not None and t != expected_title:
        issues.append(f"README: title {t!r} is not the title block title {expected_title!r}")
    todo, na = [], []
    for path in SECTIONS:
        name = " / ".join(p for p in path if p)
        if path not in found:
            issues.append(f"README: section '{name}' is missing")
            continue
        s = state(*found[path])
        if s == "todo":
            todo.append(name)
        elif s == "na":
            na.append(f"{name} ({found[path][0].splitlines()[0][4:].strip()})")
        elif s == "missing content":
            issues.append(f"README: section '{name}' is empty; write content, TODO, or N/A: <reason>")
    lines.append(f"README: {len(SECTIONS)} sections, {len(todo)} TODO, {len(na)} N/A")
    for n in na:
        lines.append(f"  N/A: {n}")
    if todo:
        (issues.append if release else lines.append)(("" if release else "NOTE: ") + f"README: TODO in {', '.join(todo)}")
    return lines, issues


def blocks(text):
    """{name: content} of the generated blocks."""
    return {m.group(2): m.group(3) for m in _BLOCK.finditer(text)}


def update(text, contents):
    """Replace the content of the generated blocks. contents: {name: text}. Returns (new text, names without a block)."""
    present = blocks(text)
    missing = [n for n in contents if n not in present]

    def repl(m):
        name = m.group(2)
        if name not in contents:
            return m.group(0)
        body = contents[name].rstrip("\n") + "\n" if contents[name].strip() else ""
        return m.group(1) + body + m.group(4)

    return _BLOCK.sub(repl, text), missing


def set_title(text, new_title):
    """Replace the first level 1 heading."""
    return re.sub(r"^# .*$", lambda _: f"# {new_title}", text, count=1, flags=re.MULTILINE)


def cell(v):
    return str(v).replace("|", "\\|").replace("\n", " ")


def table(header, rows):
    out = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    out += ["| " + " | ".join(cell(c) for c in r) + " |" for r in rows]
    return "\n".join(out)
