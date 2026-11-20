"""Extract passages describing the business from an EDGAR filing."""

import re

from lxml import etree, html

from data.edgar import PROSPECTUS_FORMS


BLOCK_ELEMENTS = {
    "article", "br", "div", "h1", "h2", "h3", "h4", "h5", "h6", "li", "p", "pre", "section", "td", "th", "tr",
}
HIDDEN_ELEMENTS = (
    "//head | //script | //style | //noscript | //*[@hidden or name()='ix:header' or name()='ix:hidden' "
    "or contains(translate(@style, ' ', ''), 'display:none')]"
)
SECTION_HEADINGS = {
    "10-K": (r"^item\s+1\b[.\s:\-–—]*business\b", r"^item\s+(?:1[abc]|2)\b"),
    "20-F": (r"^item\s+4\b[.\s:\-–—]*information\s+on\s+the\s+company\b", r"^item\s+(?:4a|5)\b"),
    **dict.fromkeys(PROSPECTUS_FORMS, (
        r"^(?:(?:our|description of)[^\S\n]+)?business(?:[^\S\n]+\d+)?$",
        r"^(?:management|our management|executive compensation)(?:[^\S\n]+\d+)?$",
    )),
}
PRODUCT_LANGUAGE = re.compile(
    r"\b(?:products?|services?|offerings?|portfolio|platforms?|brands?|"
    r"(?:we|company)\s+(?:also\s+)?(?:offer|design|develop|sell|produce|manufacture|provide)\w*)\b",
    re.IGNORECASE,
)
PASSAGE_WORDS = 150
PASSAGE_STEP = 120
PASSAGE_CHARS = 1000
MAX_PASSAGES = 6


def _visible_text(document: bytes) -> str:
    try:
        document.decode("utf-8")
        encoding = "utf-8"
    except UnicodeDecodeError:
        encoding = None
    tree = html.fromstring(document, parser=html.HTMLParser(encoding=encoding, no_network=True))
    for element in tree.xpath(HIDDEN_ELEMENTS):
        if element.getparent() is not None:
            element.drop_tree()

    parts = []
    for event, element in etree.iterwalk(tree, events=("start", "end")):
        if element.tag in BLOCK_ELEMENTS:
            parts.append("\n")
        if isinstance(element.tag, str) and event == "start":
            parts.append(element.text or "")
        if event == "end":
            parts.append(element.tail or "")
    return "\n".join(" ".join(line.split()) for line in "".join(parts).splitlines() if line.strip())


def business_passages(document: bytes, form: str) -> list[str]:
    """Return bounded excerpts, ranked by language describing products and services."""
    headings = SECTION_HEADINGS.get(form)
    if headings is None:
        return []
    try:
        text = _visible_text(document)
    except etree.ParserError:
        return []

    first_heading, next_heading = (re.compile(heading, re.IGNORECASE | re.MULTILINE) for heading in headings)
    sections = []
    starts = list(first_heading.finditer(text))
    for index, start in enumerate(starts):
        boundary = starts[index + 1].start() if index + 1 < len(starts) else len(text)
        end = next_heading.search(text, start.end(), boundary)
        sections.append(text[start.end():end.start() if end else boundary].strip())

    # The body usually repeats the title in the table of contents.
    words = max(sections, key=len, default="").split()
    passages = []
    for offset in range(0, len(words), PASSAGE_STEP):
        passage = " ".join(words[offset:offset + PASSAGE_WORDS])
        if len(passage) > PASSAGE_CHARS:
            passage = passage[:PASSAGE_CHARS].rsplit(" ", 1)[0]
        if passage:
            passages.append(passage)
    if not passages:
        return []

    ranked = sorted(range(1, len(passages)), key=lambda i: len(PRODUCT_LANGUAGE.findall(passages[i])), reverse=True)
    selected = sorted([0, *ranked[:MAX_PASSAGES - 1]])
    return [passages[i] for i in selected]
