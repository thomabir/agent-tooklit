"""S-expression reader for KiCad files (.kicad_sch, .kicad_pcb).

A node is a list: [head, arg, ...]. Strings in quotes and bare atoms are both str; numbers stay str (use float()).
"""

import re
from pathlib import Path

_TOKEN = re.compile(r'\s*(?:(\()|(\))|"((?:[^"\\]|\\.)*)"|([^\s()"]+))', re.DOTALL)


def parse(text):
    stack = [[]]
    pos = 0
    while True:
        m = _TOKEN.match(text, pos)
        if not m or m.end() == pos:
            break
        pos = m.end()
        opening, closing, quoted, atom = m.groups()
        if opening:
            stack.append([])
        elif closing:
            node = stack.pop()
            stack[-1].append(node)
        elif quoted is not None:
            stack[-1].append(re.sub(r"\\(.)", r"\1", quoted))
        else:
            stack[-1].append(atom)
    if len(stack) != 1 or len(stack[0]) != 1:
        raise ValueError("unbalanced s-expression")
    return stack[0][0]


def load(path):
    return parse(Path(path).read_text())


def children(node, head):
    """Direct child nodes with the given head."""
    return [c for c in node[1:] if isinstance(c, list) and c and c[0] == head]


def child(node, head):
    """First direct child node with the given head, or None."""
    found = children(node, head)
    return found[0] if found else None


def value(node, head, default=None):
    """First argument of the first child with the given head."""
    c = child(node, head)
    return c[1] if c is not None and len(c) > 1 else default


def xy(node, head):
    """(x, y) of a child such as (start x y), (at x y [angle]), or None."""
    c = child(node, head)
    return (float(c[1]), float(c[2])) if c is not None else None
