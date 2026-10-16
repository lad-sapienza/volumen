"""'folder' source (`source=<folder>` in the volume note): a folder of Markdown files, one file per entry -> Chapter.

The files are joined into a single text (headings shifted by one level) that goes through the chapter
Markdown reader: same tables, figures, notes and links. Here we only choose which files go in
and in what order (prefixes, exceptions) and adapt the blocks (page breaks, columns, anchors for
the [ID](ID.md) links)."""
import re
import sys
from pathlib import Path
from urllib.parse import quote, unquote

from .. import model
from ..reports import natural_key
from . import markdown, resolve_path

HEADING = re.compile(r"^(#{1,6})(\s+.*)$")
IMAGE_TARGET = re.compile(r"^(!\[.*?\]\()([^)]+)(\).*)$")


def prefix_of(cid, tokens=()):
    """-> the longest of the `tokens` prefixes (series_order / exclude_prefixes) that precedes the ID, None if none.
    After a letter another one must not follow: "S" matches S1-01, not SA-01."""
    best = None
    for tok in tokens:
        tok = str(tok)
        if cid.startswith(tok) and (tok[-1].isdigit() or not cid[len(tok):len(tok) + 1].isalpha()):
            if best is None or len(tok) > len(best):
                best = tok
    return best


def cards_dir(ch, base_dir):
    if not ch.get("dir"):
        sys.exit(f"Chapter {ch.get('id')!r}: 'dir' is missing (source: folder)")
    return resolve_path(ch["dir"], ch, base_dir, "markdown_dir")


def read_cards(folder, id_field=None):
    """-> {id: (path, meta, body)} for all the .md files of the folder. ID = `id_field` of the front matter
    (if given and present), otherwise the file name without .md."""
    out = {}
    for f in sorted(folder.glob("*.md")):
        meta, body = markdown.split_frontmatter(f.read_text(encoding="utf-8"))
        cid = str(meta.get(id_field) or f.stem) if id_field else f.stem
        out[cid] = (f, meta, body)
    return out


def card_ids(ch, base_dir):
    """Entries included in the volume (file name without .md): needed by the [text](ID.md) links from other chapters.
    An excluded entry has no destination: the link is reported as unresolved."""
    d = cards_dir(ch, base_dir)
    if not d.is_dir():
        return {}
    chosen, _ = select_cards(read_cards(d, ch.get("id_field")), ch)
    return {c: c for c in chosen}


def select_cards(cards, ch):
    """Filters and sorts according to volume.md: series_order (prefixes included, in order), exclude_prefixes,
    then the exceptions `include` / `exclude` / `first` (lists of IDs). -> (included, [(id, reason)])."""
    order = ch.get("series_order", [])
    excl = set(ch.get("exclude_prefixes", []))
    tokens = list(order) + list(excl)
    by_series = "series_order" in ch        # without series_order: no filter by series, natural order
    inc, exc_ids, first = set(ch.get("include", [])), set(ch.get("exclude", [])), list(ch.get("first", []))
    included, excluded = [], []
    for cid in cards:
        ser = prefix_of(cid, tokens)
        if cid in exc_ids:
            reason = "excluded by volume.md (exclude)"
        elif cid in inc:
            reason = None
        elif ser in excl:
            reason = "out of scope (series excluded)"
        elif by_series and (ser is None or ser not in order):
            reason = "series not listed"
        else:
            reason = None
        (excluded.append((cid, reason)) if reason else included.append(cid))
    for cid in list(inc) + first:
        if cid not in cards:
            excluded.append((cid, "listed in volume.md but has no file"))
    first = [c for c in first if c in included]
    def key(cid):
        ser = prefix_of(cid, tokens)
        return (order.index(ser) if ser in order else len(order), natural_key(cid))
    included.sort(key=key)
    return first + [c for c in included if c not in first], excluded


def _body_for_bundle(card_path, body):
    """Headings shifted by one level (# ID -> ## ID: the chapter has its own title) and images with
    absolute path (relative to the entry, not to the chapter)."""
    lines, in_code = [], False
    for ln in body.splitlines():
        if ln.startswith("```"):
            in_code = not in_code
        m = HEADING.match(ln) if not in_code else None
        if m:
            ln = "#" + ln
        else:
            im = IMAGE_TARGET.match(ln.strip())
            if im:
                target = unquote(im.group(2).strip().strip("<>"))
                if not Path(target).is_absolute():
                    ln = f"{im.group(1)}<{quote(str((card_path.parent / target).resolve()))}>{im.group(3)}"
        lines.append(ln)
    return "\n".join(lines)


def load_chapter(cfg, ch, base_dir, an, only=None):
    """'folder' chapter -> (Chapter, n_entries, excluded)."""
    cid = str(ch.get("id", ""))
    folder = cards_dir(ch, base_dir)
    if not folder.is_dir():
        sys.exit(f"Chapter {cid!r}: folder not found: {folder}")
    cards = read_cards(folder, ch.get("id_field"))
    chosen, excluded = select_cards(cards, ch)
    if only:
        chosen = [c for c in chosen if c in set(only)]
    parts = []
    for c in chosen:
        path, _meta, body = cards[c]
        parts.append(_body_for_bundle(path, body).strip())
    text = "\n\n".join(parts) + "\n"
    chapter = markdown.load_chapter(cfg, {**ch, "images": ch.get("images", "")}, base_dir, an,
                                    text=text, md_path=folder / f"{cid or 'cards'}.md")

    lvl = int(ch.get("base_level", ch.get("chapter_level", 1)))
    card_lvl = lvl + 1
    columns = int(ch.get("columns", 1))
    page_break = bool(ch.get("page_break_per_item", False))
    ids = set(chosen)
    blocks, seen_card = [], False
    for b in chapter.blocks:
        if isinstance(b, model.Heading) and b.level == card_lvl and b.text in ids:
            b.anchor = b.text
            if page_break and seen_card:
                b.page_break_before = True
            seen_card = True
        if isinstance(b, model.Text) and columns > 1:
            b.columns = columns
        blocks.append(b)
    chapter.blocks = blocks
    chapter.column_flow = 1                      # the columns apply only to the text of the entries
    return chapter, len(chosen), excluded
