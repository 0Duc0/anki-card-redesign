"""Tiny lossless HTML tree for Anki field fragments (stdlib only).

parse() keeps the original text of every tag, entity and text run, so
serialize(parse(s).children) == s for the markup found in these fields.
Edited or newly created nodes are serialized from tag/attrs.
"""

from __future__ import annotations

from html import escape
from html.parser import HTMLParser

VOID = {"br", "img", "hr", "input", "meta", "link", "source", "wbr", "col", "area", "base", "embed", "param", "track"}


class Node:
    def __init__(self, tag: str | None = None, attrs: dict[str, str] | None = None,
                 text: str = "", raw_start: str | None = None, raw_end: str | None = None):
        self.tag = tag
        self.attrs = dict(attrs or {})
        self.children: list[Node] = []
        self.text = text            # raw text for text nodes (tag is None)
        self.raw_start = raw_start  # original start tag, kept for exact round trips
        self.raw_end = raw_end      # original end tag ("" when the source omitted it)
        self.parent: Node | None = None

    # -- queries -----------------------------------------------------------
    @property
    def classes(self) -> set[str]:
        return set(self.attrs.get("class", "").split())

    def iter(self):
        for c in self.children:
            yield c
            yield from c.iter()

    def find_all(self, cls: str | None = None, tag: str | None = None) -> list[Node]:
        return [n for n in self.iter() if n.tag is not None
                and (cls is None or cls in n.classes) and (tag is None or n.tag == tag)]

    def find(self, cls: str | None = None, tag: str | None = None) -> Node | None:
        found = self.find_all(cls, tag)
        return found[0] if found else None

    def elements(self) -> list[Node]:
        """Direct element children (no text nodes)."""
        return [c for c in self.children if c.tag is not None]

    def text_content(self) -> str:
        if self.tag is None:
            return _unescape(self.text)
        return "".join(c.text_content() for c in self.children)

    # -- output ------------------------------------------------------------
    def start_tag(self) -> str:
        if self.raw_start is not None:
            return self.raw_start
        attrs = "".join(f' {k}="{escape(v, quote=True)}"' if v is not None else f" {k}"
                        for k, v in self.attrs.items())
        return f"<{self.tag}{attrs}>"

    def inner_html(self) -> str:
        return serialize(self.children)

    def outer_html(self) -> str:
        if self.tag is None:
            return self.text
        if self.tag in VOID:
            return self.start_tag()
        end = self.raw_end if self.raw_end is not None else f"</{self.tag}>"
        return self.start_tag() + self.inner_html() + end

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"Node({self.tag!r}, {self.attrs!r})" if self.tag else f"Text({self.text!r})"


def element(tag: str, attrs: dict[str, str] | None = None, children: list[Node] | None = None) -> Node:
    n = Node(tag, attrs)
    for c in children or []:
        c.parent = n
        n.children.append(c)
    return n


def text(raw: str) -> Node:
    """A text node; `raw` is inserted as-is (already HTML-escaped)."""
    return Node(None, text=raw)


def serialize(nodes: list[Node]) -> str:
    return "".join(n.outer_html() for n in nodes)


def _unescape(s: str) -> str:
    from html import unescape
    return unescape(s)


class _Builder(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.root = Node("#root")
        self.stack = [self.root]

    def _add(self, node: Node):
        node.parent = self.stack[-1]
        self.stack[-1].children.append(node)

    def _text(self, raw: str):
        parent = self.stack[-1]
        if parent.children and parent.children[-1].tag is None:
            parent.children[-1].text += raw
        else:
            self._add(Node(None, text=raw))

    def handle_starttag(self, tag, attrs):
        node = Node(tag, {k: (v if v is not None else "") for k, v in attrs}, raw_start=self.get_starttag_text())
        self._add(node)
        if tag not in VOID:
            node.raw_end = ""  # set when the end tag is seen
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        node = Node(tag, {k: (v if v is not None else "") for k, v in attrs}, raw_start=self.get_starttag_text())
        node.raw_end = ""
        self._add(node)

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                # close any unclosed children implicitly (raw_end stays "")
                self.stack[i].raw_end = f"</{tag}>"
                del self.stack[i:]
                return
        self._text(f"</{tag}>")  # stray end tag: keep as text so nothing is lost

    def handle_data(self, data):
        self._text(data)

    def handle_entityref(self, name):
        self._text(f"&{name};")

    def handle_charref(self, name):
        self._text(f"&#{name};")

    def handle_comment(self, data):
        self._text(f"<!--{data}-->")

    def handle_decl(self, decl):
        self._text(f"<!{decl}>")

    def unknown_decl(self, data):
        self._text(f"<![{data}]>")


def parse(fragment: str) -> Node:
    b = _Builder()
    b.feed(fragment)
    b.close()
    rest = b.rawdata if hasattr(b, "rawdata") else ""
    if rest:
        b._text(rest)
    return b.root
