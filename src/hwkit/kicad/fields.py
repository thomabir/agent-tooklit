"""Set symbol fields in a .kicad_sch file by text edits. The file keeps its KiCad formatting, so the diff shows only the changed fields."""

import re

_PROPERTY = re.compile(r'\(property "((?:[^"\\]|\\.)*)" "((?:[^"\\]|\\.)*)"')


def is_empty(v):
    """True for an empty field and for "~", the KiCad value of an empty Datasheet field."""
    return v.strip() in ("", "~")


def _quote(v):
    return v.replace("\\", "\\\\").replace('"', '\\"')


def _unquote(v):
    return re.sub(r"\\(.)", r"\1", v)


def _close(text, start):
    """Index after the parenthesis that closes the one at start. Skips quoted strings."""
    depth, i, in_str = 0, start, False
    while i < len(text):
        c = text[i]
        if in_str:
            if c == "\\":
                i += 1
            elif c == '"':
                in_str = False
        elif c == '"':
            in_str = True
        elif c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    raise ValueError("unbalanced s-expression")


def _children(text, start, end):
    """(start, end) of each direct child node of the node text[start:end]."""
    spans, i = [], start + 1
    while i < end - 1:
        c = text[i]
        if c == '"':
            i = _skip_string(text, i)
        elif c == "(":
            j = _close(text, i)
            spans.append((i, j))
            i = j
        else:
            i += 1
    return spans


def _skip_string(text, i):
    i += 1
    while text[i] != '"':
        i += 2 if text[i] == "\\" else 1
    return i + 1


def symbols(text):
    """(start, end) of each placed symbol (direct child '(symbol' of the root node; lib_symbols is not included)."""
    root = text.index("(")
    return [(s, e) for s, e in _children(text, root, _close(text, root)) if text.startswith("(symbol", s)]


def properties(text, span):
    """{name: (value, start, end)} of the direct property nodes of a symbol."""
    found = {}
    for s, e in _children(text, *span):
        m = _PROPERTY.match(text, s)
        if m:
            found[_unquote(m.group(1))] = (_unquote(m.group(2)), s, e)
    return found


def placed(text):
    """{name: value} of the properties of each placed symbol."""
    return [{k: v[0] for k, v in properties(text, span).items()} for span in symbols(text)]


def set_fields(text, match, values, after, replace=False):
    """Set fields in all placed symbols for which match(properties as {name: value}) is true.
    values: {field name: value}. A missing or empty field (see is_empty) gets the value. A field with a different value is changed only if replace is true, else it is a conflict.
    A missing field is added as a copy of the field 'after' (same position, hidden state, font) with the new name and value.
    Returns (new text, number of changed fields, conflicts as (field name, old value, new value))."""
    edits, conflicts = [], []
    for span in symbols(text):
        props = properties(text, span)
        if not match({k: v[0] for k, v in props.items()}):
            continue
        for name, value in values.items():
            if name in props:
                old, s, _ = props[name]
                if not is_empty(old) and old != value and not replace:
                    conflicts.append((name, old, value))
                elif old != value:
                    m = _PROPERTY.match(text, s)
                    edits.append((m.start(2), m.end(2), _quote(value)))
                continue
            if after not in props:
                raise KeyError(f"symbol at {span[0]}: no field '{after}' to copy for the new field '{name}'")
            _, s, e = props[after]
            line_start = text.rfind("\n", 0, s) + 1
            indent = text[line_start:s]
            node = _PROPERTY.sub(lambda _, n=name, v=value: f'(property "{_quote(n)}" "{_quote(v)}"', text[s:e], count=1)
            edits.append((e, e, f"\n{indent}{node}"))
    for s, e, new in sorted(edits, reverse=True):
        text = text[:s] + new + text[e:]
    return text, len(edits), conflicts
