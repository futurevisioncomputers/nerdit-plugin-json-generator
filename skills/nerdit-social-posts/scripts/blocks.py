"""Teaching blocks in a lesson's HTML, as plain text: what a data-first post shows word for word.

Topics are the numbered sections (<h2>N — Title</h2>). Inside them the lessons carry:
  nerdit-run      "You type" code and "You see" output
  nerdit-predict  a question, code, and the answer (output + explanation)
  nerdit-compare  a mistake and its fix, each with a head, code and a reason
  nerdit-vtable   the "meet the data" table (columns and meaning) with its caption
and once per lesson a nerdit-cheatsheet table.
"""
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "nerdit-story-video" / "scripts"))
from storyplan import marks  # noqa: E402  one <sup>/<sub> reading for the pack and its checks

VOID = {"br", "img", "hr", "input", "meta", "link", "source", "wbr", "col", "area", "base", "embed", "param", "track"}
TOPIC = re.compile(r"^\s*(\d+)\s*[—–-]")
READS = re.compile(r"read_csv\(\s*['\"]([^'\"]+)['\"]")


class Node:
    def __init__(self, tag: str, attrs: dict, parent: "Node | None"):
        self.tag, self.attrs, self.parent, self.children = tag, attrs, parent, []

    def classes(self) -> set:
        return set((self.attrs.get("class") or "").split())


class _Tree(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node("root", {}, None)
        self.cur = self.root

    def handle_starttag(self, tag, attrs):
        node = Node(tag, {k: v or "" for k, v in attrs}, self.cur)
        self.cur.children.append(node)
        if tag not in VOID:
            self.cur = node

    def handle_endtag(self, tag):
        node = self.cur
        while node is not self.root and node.tag != tag:
            node = node.parent
        if node is not self.root:
            self.cur = node.parent

    def handle_data(self, data):
        self.cur.children.append(data)


def _tree(html: str) -> Node:
    t = _Tree()
    t.feed(marks(html))
    t.close()
    return t.root


def _raw(node: Node) -> str:
    """All text under a node, as written; Copy buttons left out."""
    out = []
    for c in node.children:
        if isinstance(c, str):
            out.append(c)
        elif not (c.tag == "button" or "nerdit-copy-btn" in c.classes()):
            out.append(_raw(c))
    return "".join(out)


def _text(node: Node | None) -> str:
    return " ".join(_raw(node).split()) if node is not None else ""


def _find(node: Node, test, deep: bool = True) -> list:
    found = []
    for c in node.children:
        if isinstance(c, Node):
            if test(c):
                found.append(c)
                if not deep:
                    continue
            found += _find(c, test, deep)
    return found


def _first(node: Node | None, test) -> "Node | None":
    if node is None:
        return None
    hits = _find(node, test)
    return hits[0] if hits else None


def _cls(name: str):
    return lambda n: name in n.classes()


def _tag(name: str):
    return lambda n: n.tag == name


def _code(pre: Node | None) -> str:
    """The code a learner sees in a <pre>: its <code> text, entities decoded, newlines kept."""
    if pre is None:
        return ""
    code = _first(pre, _tag("code")) or pre
    return _raw(code).strip("\n")


def plain(fragment: str) -> str:
    """Text of an HTML fragment; inside <pre> newlines are kept, elsewhere whitespace is collapsed."""
    root = _tree(fragment)
    pre = _first(root, _tag("pre"))
    if pre is not None and _text(root) == _text(pre):
        return _code(pre)
    return _text(root)


def _direct(node: Node, test) -> list:
    return [c for c in node.children if isinstance(c, Node) and test(c)]


def _table(table: Node) -> tuple[list, list]:
    headers = [_text(th) for th in _find(table, _tag("th"))]
    rows = []
    for tr in _find(table, _tag("tr")):
        cells = [_text(td) for td in _direct(tr, _tag("td"))]
        if cells:
            rows.append(cells)
    return headers, rows


def _run(node: Node, index: int) -> dict:
    pre_in = _first(_first(node, _cls("nerdit-in")), _tag("pre"))
    out = _first(node, _cls("nerdit-out"))
    code = _code(pre_in)
    return {"kind": "run", "index": index, "lang": (pre_in.attrs.get("data-lang") if pre_in else "") or "",
            "code": code, "output": _code(_first(out, _tag("pre"))), "outTag": _text(_first(out, _cls("nerdit-tag"))),
            "reads": [m.split("/")[-1] for m in READS.findall(code)]}


def _predict(node: Node, index: int) -> dict:
    answer = _first(node, _cls("nerdit-predict-answer"))
    pre = next((p for p in _find(node, _tag("pre")) if answer is None or p not in _find(answer, _tag("pre"))), None)
    return {"kind": "predict", "index": index, "question": _text(next(iter(_direct(node, _tag("p"))), None)),
            "lang": (pre.attrs.get("data-lang") if pre else "") or "", "code": _code(pre),
            "output": _code(_first(_first(answer, _cls("nerdit-out")), _tag("pre"))),
            "outTag": _text(_first(_first(answer, _cls("nerdit-out")), _cls("nerdit-tag"))),
            "explanation": " ".join(_text(p) for p in _find(answer, _tag("p"))) if answer is not None else ""}


def _side(node: Node | None) -> dict:
    pre = _first(node, _tag("pre"))
    return {"head": _text(_first(node, _cls("nerdit-compare-head"))), "code": _code(pre),
            "lang": (pre.attrs.get("data-lang") if pre else "") or "",
            "reason": " ".join(_text(p) for p in _find(node, _tag("p"))) if node is not None else ""}


def _spot(table: Node, index: int) -> dict:
    headers, rows = _table(table)
    figure = table.parent
    caption = _first(figure, _cls("nerdit-figure-caption")) if figure is not None else None
    return {"kind": "spot", "index": index, "headers": headers, "rows": rows, "caption": _text(caption)}


def lesson_blocks(html: str) -> dict:
    root = _tree(html)
    topics: dict = {}
    counts = {"run": 0, "predict": 0, "compare": 0, "spot": 0}
    cheat = None
    current = None

    def walk(node: Node) -> None:
        nonlocal current, cheat
        for c in node.children:
            if not isinstance(c, Node):
                continue
            cls = c.classes()
            if c.tag == "h2":
                m = TOPIC.match(_text(c))
                current = int(m.group(1)) if m else current
                if m:
                    topics.setdefault(current, {"run": [], "predict": [], "compare": [], "spot": []})
                continue
            if "nerdit-cheatsheet" in cls:
                table = _first(c, _tag("table"))
                if table is not None and cheat is None:
                    headers, rows = _table(table)
                    cheat = {"kind": "cheatsheet", "headers": headers, "rows": rows}
                continue
            kind = ("run" if "nerdit-run" in cls else "predict" if "nerdit-predict" in cls
                    else "compare" if "nerdit-compare" in cls else "spot" if (c.tag == "table" and "nerdit-vtable" in cls) else None)
            if kind:
                if current is not None:
                    make = {"run": _run, "predict": _predict, "spot": _spot}.get(kind)
                    block = make(c, counts[kind]) if make else {
                        "kind": "compare", "index": counts[kind],
                        "bad": _side(_first(c, _cls("nerdit-compare-bad"))), "good": _side(_first(c, _cls("nerdit-compare-good")))}
                    topics[current][kind].append(block)
                    counts[kind] += 1
                continue
            walk(c)

    walk(root)
    return {"topics": topics, "cheatsheet": cheat}
