"""Intermediate model of the volume: what the sources produce and the renderers consume."""
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# Inline footnote: the source replaces [^n] with NOTE_OPEN + note text + NOTE_CLOSE;
# the renderers turn it into a real note (Typst #footnote, Word footnotes.xml).
NOTE_OPEN, NOTE_CLOSE = "\x03", "\x04"
NOTE = re.compile(f"{NOTE_OPEN}(.*?){NOTE_CLOSE}", re.S)
# Link to another chapter: LINK_OPEN + chapter id + "|" + text + LINK_CLOSE (clickable, without changing the look)
LINK_OPEN, LINK_CLOSE = "\x05", "\x06"
CHLINK = re.compile(f"{LINK_OPEN}([^|{LINK_CLOSE}]*)\\|(.*?){LINK_CLOSE}", re.S)


def strip_chapter_links(text):
    """Removes the markers of links between chapters, keeping the text (where the link is not supported)."""
    return CHLINK.sub(lambda m: m.group(2), text) if isinstance(text, str) and LINK_OPEN in text else text


def chapter_anchor(cid):
    """Label/bookmark name of the chapter: only letters, digits and '_' (valid in Typst and Word)."""
    return "ch_" + re.sub(r"\W", "_", str(cid))

# bold/italic: italic with _ only at word edges (not inside URLs or names_with_underscores)
# strikethrough: ~~text~~
# highlight: ==text== (Obsidian/Pandoc mark) or [text]{.mark} (Pandoc span)
# annotations (CriticMarkup): {==text==}{>>comment<<} on a passage, {>>comment<<} point
INLINE_MD = re.compile(r"(\{\+\+[^\n]*?\+\+\}|\{--[^\n]*?--\}|\{~~[^\n]*?~>[^\n]*?~~\}|\{==[^\n]*?==\}\{(?:[A-Za-z_]+=\"[^\"\n]*\"\s*)*>>[^\n]*?<<\}|\{(?:[A-Za-z_]+=\"[^\"\n]*\"\s*)*>>[^\n]*?<<\}|~~[^~\n]+~~|==(?!=)(?:[^=\n]|=(?!=))+==|\[[^\]\n]+\]\{\.mark\}|\*\*[^*]+\*\*|\^[^^\s]+\^|\*[^*]+\*|(?<![\w\\])_[^_]+_(?!\w))")


@dataclass
class Heading:
    level: int                    # 1..5, matches the styles h1..h5
    text: str
    page_break_before: bool = False
    anchor: Optional[str] = None  # id of an internal link (e.g. entry of a complex): [text](ID.md)


@dataclass
class Text:
    """Paragraphs separated by an empty line; single line breaks = line break; inline markup **/*/_."""
    text: str
    columns: int = 1              # >1: multi-column text (only where the renderer supports it)


@dataclass
class StyledText:
    """One or more paragraphs (separated by an empty line) with a custom style (`::: {attributes}`).
    style: dictionary resolved by styled.resolve (font, size, bold, align, space_before, ...)."""
    text: str
    style: dict


@dataclass
class PageBreak:
    """New page (`---` line in the frontmatter files)."""


@dataclass
class Figure:
    path: Path
    caption: str                  # already complete and numbered ("Fig. 6.3.1. ...")
    klass: Optional[str] = None   # figure class (`{class=plan}`): measures and spacing from config images.classes.<klass>
    width: Optional[str] = None   # "12cm", "60%", "3in" ... (% of the available width)
    height: Optional[str] = None
    position: Optional[str] = None   # auto | top | bottom | column | left | right (multi-column Typst only)
    wrap: int = 1                 # with position left/right: how many following paragraphs wrap around
    group: Optional[str] = None   # 'end': end-of-section figure (consecutive ones become a FigureGroup)
    align: Optional[str] = None   # left | center | right (frontmatter images; default: centre)


@dataclass
class FigureGroup:
    """End-of-chapter/section figures. With title: dedicated section (title page)."""
    figures: list
    title: Optional[str] = None


@dataclass
class Table:
    """Generic table (e.g. from Markdown): header + rows; cells with inline markup.
    ratios = relative column weights (None = equal); aligns = 'left'|'center'|'right' per column."""
    header: list
    rows: list
    ratios: Optional[list] = None
    aligns: Optional[list] = None
    caption: str = ""             # numbered, above the table
    klass: Optional[str] = None   # table class (`{.name}` line after the table): config table.classes.<name>


@dataclass
class Quote:
    """Quotation (blockquote); source = reference on a separate line, after the long dash."""
    text: str
    source: Optional[str] = None


@dataclass
class ListBlock:
    items: list                   # [(depth, text)], depth 0 = first level
    ordered: bool = False


@dataclass
class PartTitle:
    """Page on its own with only the title, centred (chapter container)."""
    level: int
    text: str


@dataclass
class Chapter:
    id: str
    title: str
    blocks: list = field(default_factory=list)
    new_page: bool = True         # the chapter starts on a new page
    running_title: str = ""       # text of the running head (default: title)
    authors: list = field(default_factory=list)   # authors of the chapter (grey line under the h1 title)
    bibliography: bool = True     # adds the bibliography of the cited works at the end of the chapter
    column_flow: int = 1          # >1: after the title, the whole chapter in a single column flow
    front: bool = False           # title page/colophon: without title, running head and page number


@dataclass
class Volume:
    meta: dict
    chapters: list
    front: list = field(default_factory=list)    # frontmatter (Chapter with front=True), before the table of contents


@dataclass
class Bibliography:
    """Bibliographic references cited in the chapter (already formatted by the CSL style)."""
    title: str
    level: int
    entries: list                 # [(key, text with inline markup *italic*)]


def map_text(blocks, fn):
    """Applies fn to every text of the blocks (paragraphs, quotations, lists, tables, captions,
    headings). fn(str) -> str."""
    for b in blocks:
        if isinstance(b, (Heading, Text, StyledText)):
            b.text = fn(b.text)
        elif isinstance(b, Quote):
            b.text = fn(b.text)
            b.source = fn(b.source) if b.source else b.source
        elif isinstance(b, ListBlock):
            b.items = [(d, fn(t)) for d, t in b.items]
        elif isinstance(b, Table):
            b.header = [fn(c) for c in b.header]
            b.rows = [[fn(c) for c in r] for r in b.rows]
            b.caption = fn(b.caption) if b.caption else b.caption
        elif isinstance(b, Figure):
            b.caption = fn(b.caption)


_UNITS = {"cm": 1.0, "mm": 0.1, "in": 2.54, "pt": 2.54 / 72, "px": 2.54 / 96}


def length_cm(spec, ref_cm):
    """'12cm', '5in', '300px', '60%' (of ref_cm) -> cm; None if empty or invalid."""
    if not spec:
        return None
    m = re.fullmatch(r"\s*([0-9]*\.?[0-9]+)\s*(cm|mm|in|pt|px|%)?\s*", str(spec))
    if not m:
        return None
    v, unit = float(m.group(1)), m.group(2) or "cm"
    return ref_cm * v / 100 if unit == "%" else v * _UNITS[unit]


MARK = re.compile(r"^(?:==(.+)==|\[(.+)\]\{\.mark\})$", re.S)


def mark_text(part):
    """If `part` is a highlight (==t== / [t]{.mark}) -> the inner text, otherwise None."""
    m = MARK.match(part)
    return (m.group(1) or m.group(2)) if m else None


CRITIC = re.compile(r"^(?:\{==(.*?)==\}\{(?:[A-Za-z_]+=\"[^\"\n]*\"\s*)*>>(.*?)<<\}|\{(?:[A-Za-z_]+=\"[^\"\n]*\"\s*)*>>(.*?)<<\})$", re.S)

# state of annotations (set by the CLI: --annotations or config `annotations`)
ANNOT = {"enabled": False, "author": "", "initials": "", "color": "FFD54F", "items": [],
         "suggestions": "accept"}     # without --annotations the suggestions {++ ++} {-- --} {~~ ~> ~~}: "accept" | "reject"

CRITIC_EDIT = re.compile(r"^(?:\{\+\+(.*?)\+\+\}|\{--(.*?)--\}|\{~~(.*?)~>(.*?)~~\})$", re.S)


def critic_edit(part):
    """If `part` is a CriticMarkup suggestion -> (old text, new text), otherwise None:
    {++new++} -> ("", new); {--old--} -> (old, ""); {~~old~>new~~} -> (old, new)."""
    m = CRITIC_EDIT.match(part)
    if not m:
        return None
    if m.group(1) is not None:
        return "", m.group(1)
    if m.group(2) is not None:
        return m.group(2), ""
    return m.group(3), m.group(4)


def accepted_edit(old, new):
    """Text that remains without --annotations (annotations.suggestions: accept = new, reject = old)."""
    return old if ANNOT["suggestions"] == "reject" else new


def critic_parts(part):
    """If `part` is a CriticMarkup annotation -> (annotated text or "", comment), otherwise None."""
    m = CRITIC.match(part)
    if not m:
        return None
    return (m.group(1) or "", (m.group(2) if m.group(1) is not None else m.group(3)) or "")


def annotation_tag(n):
    """Invisible marker (ASCII only) that the PDF carries to find where to anchor the annotation."""
    return f"ZQA{n:04d}QZ"


def running_left(chapter, volume, hcfg):
    """Text of the running head of even (left) pages: header.left_pages = "author" (default:
    the chapter's authors, otherwise the volume's) or "title" (like the right pages)."""
    if hcfg.get("left_pages", "author") != "author":
        return None
    names = list(chapter.authors) or [
        str(a.get("name", "")) if isinstance(a, dict) else str(a)
        for a in (volume.meta.get("authors") or [])]
    return ", ".join(n for n in names if n)
