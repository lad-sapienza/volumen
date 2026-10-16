"""'markdown' source: one .md file per chapter -> blocks of the model.

YAML frontmatter (title, ...); `#`/`##`/`###` headings, paragraphs, images
`![caption](file)` on a line of their own. Not yet handled (reported as anomalies):
footnotes, quotations, tables, lists."""
import re
import sys
from itertools import count
from pathlib import Path

import yaml
from urllib.parse import unquote

from .. import model, styled
from . import resolve_path

FRONTMATTER = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.S)
HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
UNESCAPE = re.compile(r"\\([\\`{}\[\]()#+.!|<>~^$_*-])")
QUOTE_LINE = re.compile(r"^\s{0,3}>\s?(.*)$")
QUOTE_SOURCE = re.compile(r"^(?:—|―|--)\s*(.+)$")     # last line of the quotation: "— source"
DASH = "-\u2013\u2014\u2212"        # hyphen, en dash, em dash, minus: Word/Obsidian substitute them
TABLE_DELIM = re.compile(rf"^\s*\|?\s*:?[{DASH}]{{2,}}:?\s*(\|\s*:?[{DASH}]{{2,}}:?\s*)*\|?\s*$")
DELIM_CELL = re.compile(rf"^:?[{DASH}]{{2,}}:?$")
TABLE_CAPTION = re.compile(r"^(?:Table\s*:|:)\s*(.+)$")
TABLE_CLASS = re.compile(r"^\{\.([\w-]+)\}$")
LIST_ITEM = re.compile(r"^(\s*)([-*+]|\d+[.)])\s+(.*)$")
IMAGE_LINE = re.compile(r"^!\[(.*?)\]\((.+?)\)(?:\{([^}]*)\})?\s*$")   # Pandoc attributes: {#label width=..}
LINK = re.compile(r"(?<!!)\[([^\]]+)\]\((?:#|https?://)[^)]*\)")
INTERNAL = re.compile(r"(?<!!)\[([^\]]*)\]\(#([^)\s]+)\)")     # internal reference [text](#label)
LABEL_ID = re.compile(r"#([^\s}]+)")                               # #label in {..} or []{#..}
REF_OPEN, REF_CLOSE = "\x01", "\x02"                              # reference placeholder, resolved at the end of the chapter
BARE_LINK = re.compile(r"(?<!!)\[([^\]]*)\]\(([A-Za-z0-9_\-]+)\)")   # [text](slug): .md is missing, the link is not resolved
MDLINK = re.compile(r"(?<!!)\[([^\]]*)\]\(<?([^)<>]*?\.md)(?:#[^)>]*)?>?\)")   # [text](file.md) [text](file.md#section)
DIV_OPEN = re.compile(r"^:{3,}\s*(\{.*\})\s*$")        # ::: {.style size=28 align=center}
DIV_CLOSE = re.compile(r"^:{3,}\s*$")
VAR = re.compile(r"\{\{\s*([\w.-]+)\s*\}\}")                # {{title}}, {{authors}}: values from volume.md
ANCHOR = re.compile(r"\[\]\{[^}]*\}")                                # Word/Pandoc anchors: []{#_Ref123 .anchor}


def split_frontmatter(text):
    m = FRONTMATTER.match(text)
    if not m:
        return {}, text
    fm = m.group(1).replace("\t", "  ")      # TABs are not valid YAML (Obsidian inserts them in lists)
    try:
        meta = yaml.safe_load(fm) or {}
    except yaml.YAMLError:
        # hand-written frontmatter (e.g. title with an unquoted ':'): 'key: value' line by line
        meta = {}
        for ln in fm.splitlines():
            if ":" in ln and not ln.startswith((" ", "-")):
                k, v = ln.split(":", 1)
                meta[k.strip()] = v.strip().strip("\"'")
    return meta, text[m.end():]


ATTR = re.compile(r'([\w-]+)=("[^"]*"|\'[^\']*\'|\S+)')


def parse_attrs(text):
    """{#id width=12cm position=right} -> {'width': '12cm', 'position': 'right'} (id separate)."""
    return {k: v.strip("\"'") for k, v in ATTR.findall(text or "")}


def join_wrapped_images(lines, max_lines=12):
    """Pandoc wraps long captions: `![text\\ncontinues](file){attr}` over several lines.
    Joins them into one line (up to the end of the image syntax)."""
    out, i = [], 0
    while i < len(lines):
        line = lines[i]
        if line.lstrip().startswith("![") and not IMAGE_LINE.match(line.strip()):
            for j in range(i + 1, min(i + max_lines, len(lines))):
                cand = " ".join(x.strip() for x in lines[i:j + 1])
                if IMAGE_LINE.match(cand):
                    line, i = cand, j
                    break
        out.append(line)
        i += 1
    return out


NOTE_DEF = re.compile(r"^\[\^([^\]]+)\]:\s*(.*)$")
NOTE_REF = re.compile(r"\[\^([^\]]+)\]")


def extract_notes(lines):
    """Removes the `[^id]: text` definitions (with indented continuations) and returns them separately.
    -> (lines without definitions, {id: text})"""
    out, notes, i = [], {}, 0
    while i < len(lines):
        m = NOTE_DEF.match(UNESCAPE.sub(r"\1", lines[i]).strip())
        if not m:
            out.append(lines[i])
            i += 1
            continue
        parts = [m.group(2).strip()]
        i += 1
        while i < len(lines):
            ln = lines[i]
            if ln.strip() and not NOTE_DEF.match(ln.strip()) and not ln.lstrip().startswith(("|", "#")):
                parts.append(ln.strip())          # continuation (indented or "lazy")
                i += 1
            elif not ln.strip() and i + 1 < len(lines) and lines[i + 1][:1] in (" ", "\t") \
                    and lines[i + 1].strip():
                i += 1                            # empty line + indented paragraph: same note
            else:
                break
        notes[m.group(1)] = " ".join(p for p in parts if p)
    return out, notes


def split_row(line, prep=None):
    """Cell by cell, without splitting on `\\\\|` (literal pipes); then removes the escapes."""
    cells = re.split(r"(?<!\\)\|", line.strip())
    if cells and not cells[0].strip():
        cells = cells[1:]
    if cells and not cells[-1].strip():
        cells = cells[:-1]
    prep = prep or (lambda t: LINK.sub(r"\1", INTERNAL.sub(lambda m: f"{REF_OPEN}{m.group(2)}|{m.group(1)}{REF_CLOSE}",
                                                            UNESCAPE.sub(r"\1", t))))
    return [prep(c.strip()) for c in cells]


def column_aligns(delim_line):
    out = []
    for c in split_row(delim_line, prep=lambda t: t):
        c = c.strip()
        out.append("center" if c.startswith(":") and c.endswith(":") else
                   "right" if c.endswith(":") else "left")
    return out


def column_ratios(header, rows):
    """Column weights from the content: more text = wider column (with limits)."""
    ratios = []
    for i in range(len(header)):
        lens = [len(header[i])] + [len(r[i]) for r in rows if i < len(r)]
        w = 0.6 * max(lens) + 0.4 * (sum(lens) / len(lens))
        ratios.append(round(max(6, min(45, w)), 1))
    return ratios


def resolve_refs(blocks, labels, cid, fname, an):
    """[text](#label) -> 'Fig. 4.2' / 'Table 4.1' if the label is a figure/table of the
    chapter; otherwise the link text stays and it is reported."""
    pat = re.compile(f"{REF_OPEN}([^|{REF_CLOSE}]*)\\|([^{REF_CLOSE}]*){REF_CLOSE}")

    def sub(text):
        if not isinstance(text, str) or REF_OPEN not in text:
            return text

        def one(m):
            ident, shown = m.group(1), m.group(2)
            if ident in labels:
                return labels[ident]
            an.add(cid, "unresolved internal reference", fname, f"#{ident} ({shown[:30]})")
            return shown
        return pat.sub(one, text)

    for b in blocks:
        if isinstance(b, model.Heading):
            b.text = model.strip_chapter_links(sub(b.text))      # headings have no inline markup
        elif isinstance(b, model.Text):
            b.text = sub(b.text)
        elif isinstance(b, model.Quote):
            b.text, b.source = sub(b.text), sub(b.source)
        elif isinstance(b, model.ListBlock):
            b.items = [(d, sub(t)) for d, t in b.items]
        elif isinstance(b, model.Table):
            b.header = [sub(c) for c in b.header]
            b.rows = [[sub(c) for c in r] for r in b.rows]
            b.caption = sub(b.caption)
        elif isinstance(b, model.Figure):
            b.caption = sub(b.caption)


def find_image(name, dirs):
    for n in (name, unquote(name).strip("<>")):      # Obsidian encodes spaces (%20)
        for d in dirs:
            p = Path(n).expanduser() if Path(n).is_absolute() else d / n
            if p.exists():
                return p
    return None


def group_end_figures(blocks, ch):
    """Consecutive figures with `group=end` (end of section) -> FigureGroup."""
    if ch.get("end_images_placement", "after_item") == "figures_section":
        print("Note: end_images_placement=figures_section is not supported "
              "(end-of-section figures stay where they are).", file=sys.stderr)
    out, run = [], []
    for b in blocks:
        if isinstance(b, model.Figure) and b.group == "end":
            run.append(b)
            continue
        if run:
            out.append(model.FigureGroup(run))
            run = []
        out.append(b)
    if run:
        out.append(model.FigureGroup(run))
    return out


def load_chapter(cfg, ch, base_dir, an, text=None, md_path=None):
    """text/md_path: text already read (e.g. the files of a folder, joined into a single text)."""
    cid = str(ch.get("id", ""))
    if text is None:
        if not ch.get("file"):
            sys.exit(f"Chapter {cid!r}: 'file' is missing (source: markdown)")
        md_path = resolve_path(ch["file"], ch, base_dir, "markdown_dir")
    if text is None and not md_path.exists():
        # the chapter stays in the volume with the title only, and the missing file is reported
        an.add(cid, "Markdown file missing", "file", str(md_path))
        return model.Chapter(cid, ch.get("title", cid),
                             [model.Heading(int(ch.get("base_level", ch.get("chapter_level", 1))),
                                            str(ch.get("title") or cid))],
                             new_page=bool(ch.get("new_page", True)))
    meta, body = split_frontmatter(md_path.read_text(encoding="utf-8") if text is None else text)
    front = bool(ch.get("front"))            # title page/colophon: no title, `---` = new page
    if ch.get("vars") and "{{" in body:
        def one(m):
            v = ch["vars"].get(m.group(1))
            if v is None:
                an.add(cid, "variable {{..}} not defined in volume.md", md_path.name, m.group(0))
                return m.group(0)
            return str(v)
        body = VAR.sub(one, body)
    title = str(meta.get("title") or ch.get("title") or cid)

    # default: {sources.images_dir}/{id}/ if defined; otherwise only next to the .md file
    default_images = "{images_dir}/{id}" if ch.get("sources", {}).get("images_dir") else None
    images = ch.get("images", default_images)
    search = ([resolve_path(images, ch, base_dir)] if images else []) + [md_path.parent]
    icfg_classes = cfg.get("images", {}).get("classes", {})

    lvl = int(ch.get("base_level", ch.get("chapter_level", 1)))
    prefix = str(ch.get("figure_prefix", cid))
    fig_counter = count(1)
    blocks = [] if front else [model.Heading(lvl, title)]

    paras, cur = [], []   # paragraphs being accumulated between one block and the next

    def flush_par():
        if cur:
            paras.append(" ".join(cur))
            cur.clear()

    def flush_text():
        flush_par()
        if paras:
            blocks.append(model.Text("\n\n".join(paras)))
            paras.clear()

    table_lines = []           # raw lines of a pipe table in progress
    table_counter = count(1)
    labels = {}                # label -> "Fig. 4.2" / "Table 4.1" (for internal references)
    quote, items = [], []      # blockquote in progress; list items in progress (depth, text)
    ordered = False

    def flush_quote():
        if not quote:
            return
        lines = list(quote)
        quote.clear()
        source = None
        while lines and not lines[-1].strip():
            lines.pop()
        if lines and QUOTE_SOURCE.match(lines[-1].strip()):
            source = QUOTE_SOURCE.match(lines.pop().strip()).group(1)
        text = "\n\n".join(" ".join(p.split("\n")).strip()
                            for p in re.split(r"\n\s*\n", "\n".join(lines).strip()) if p.strip())
        blocks.append(model.Quote(text, source))

    def explode_collapsed(line):
        """Table pasted on ONE line (`| a | b | | :-- | :-- | | 1 | 2 |`): rebuilds the rows.
        Between two rows there is exactly one empty cell (`| |`); the header row ends where
        the separator row begins."""
        cells = [c.strip() for c in re.split(r"(?<!\\)\|", line.strip())][1:-1]
        first = next((i for i, c in enumerate(cells) if DELIM_CELL.match(c)), None)
        if not first or first < 2 or cells[first - 1] != "":
            return None
        n = first - 1                                   # columns = cells before the empty cell
        rows = [cells[:n]]
        i = first
        while i < len(cells):
            rows.append(cells[i:i + n])
            i += n + 1                                  # +1: the empty separator cell
        if any(len(r) != n for r in rows):
            return None
        return ["| " + " | ".join(r) + " |" for r in rows]

    def flush_table():
        if not table_lines:
            return
        lines = list(table_lines)
        table_lines.clear()
        if len(lines) == 1:
            lines = explode_collapsed(lines[0]) or lines
        if len(lines) >= 2 and TABLE_DELIM.match(lines[1]):
            header = split_row(lines[0], prep)
            rows = []
            for ln in lines[2:]:
                r = split_row(ln, prep)
                r = (r + [""] * len(header))[:len(header)]      # short/long rows: they adapt
                rows.append(r)
            aligns = (column_aligns(lines[1]) + ["left"] * len(header))[:len(header)]
            blocks.append(model.Table(header, rows, column_ratios(header, rows), aligns))
        else:
            an.add(cid, "Markdown table not recognized (the --- row is missing)", md_path.name, lines[0][:40])
            cur.extend(x.strip() for x in lines)

    def flush_list():
        if items:
            blocks.append(model.ListBlock(list(items), ordered))
            items.clear()

    body_lines, note_defs = extract_notes(join_wrapped_images(body.splitlines()))
    used_notes = set()

    chapter_ids = ch.get("chapter_ids", {})

    def chapter_links(text):
        """[text](file-name.md) -> link to another chapter, resolved with its id ("6.2"):
        "[ch. {nr}](f.md)" -> "ch. 6.2"; "[ch.](f.md)" -> "ch. 6.2"; "[](f.md)" or text equal
        to the file name (Obsidian's default) -> "6.2". The #section part is ignored.
        File not in volume.md: reported, the text stays."""
        def one(m):
            shown, target = m.group(1).strip(), unquote(m.group(2)).strip()
            stem = Path(target).stem
            cid_ = chapter_ids.get(stem)
            if cid_ is None:
                an.add(cid, "unresolved chapter link", md_path.name, f"({target})")
                return shown or stem
            if "{nr}" in shown:
                label = shown.replace("{nr}", cid_)
            else:
                label = cid_ if shown in ("", stem, target, Path(target).name) else f"{shown} {cid_}"
            return f"{model.LINK_OPEN}{cid_}|{label}{model.LINK_CLOSE}"
        for m in BARE_LINK.finditer(text):
            an.add(cid, "link without .md extension", md_path.name, f"({m.group(2)}): write ({m.group(2)}.md)")
        return MDLINK.sub(one, text) if ".md" in text else text

    def prep(text):
        """Text -> ready text: removes escapes, [^n] -> inline note, internal references, links."""
        text = chapter_links(UNESCAPE.sub(r"\1", text))

        def note(m):
            key = m.group(1)
            if key not in note_defs:
                an.add(cid, "undefined footnote", md_path.name, f"[^{key}]")
                return ""
            used_notes.add(key)
            body_ = prep_note(note_defs[key])
            return f"{model.NOTE_OPEN}{body_}{model.NOTE_CLOSE}"
        text = NOTE_REF.sub(note, text)
        text = INTERNAL.sub(lambda m: f"{REF_OPEN}{m.group(2)}|{m.group(1)}{REF_CLOSE}", text)
        return LINK.sub(r"\1", text)

    def prep_note(text):
        text = chapter_links(UNESCAPE.sub(r"\1", text))
        text = INTERNAL.sub(lambda m: f"{REF_OPEN}{m.group(2)}|{m.group(1)}{REF_CLOSE}", text)
        text = LINK.sub(r"\1", text)
        return text.replace(model.NOTE_OPEN, "").replace(model.NOTE_CLOSE, "")

    div = None                 # `::: {attributes}` block in progress: (style, [lines])
    div_align = None           # alignment of the block an image is in

    def close_div():
        classes_style, lines = div
        paras, cur_p = [], []
        for ln in lines + [""]:
            if ln.strip():
                cur_p.append(ln.strip())
            elif cur_p:
                paras.append(" ".join(cur_p))
                cur_p = []
        if paras:
            blocks.append(model.StyledText("\n\n".join(paras), classes_style))

    for raw in body_lines:
        # blocks with a custom style
        if div is not None:
            if DIV_CLOSE.match(raw.strip()):
                close_div()
                div, div_align = None, None
                continue
            if IMAGE_LINE.match(prep(raw.rstrip()).strip()):
                # image inside the block: closes the text first, then treats it as a normal image; the text
                # after continues with the same style (without repeating margin-top) and the image inherits its alignment
                close_div()
                div_align = div[0].get("align")
                div = ({**div[0], "space_before": 0}, [])
            else:
                div[1].append(prep(raw.rstrip()))
                continue
        dm = DIV_OPEN.match(raw.strip())
        if dm:
            flush_table()
            flush_text()
            flush_quote()
            flush_list()
            classes, attrs = styled.parse_attrs(dm.group(1))
            div = (styled.resolve(cfg, classes, attrs,
                                  warn=lambda msg: an.add(cid, "custom style", md_path.name, msg)), [])
            continue
        if ch.get("pages") and raw.strip() == "---":
            flush_table()
            flush_text()
            flush_quote()
            flush_list()
            blocks.append(model.PageBreak())
            continue
        # Obsidian/Zotero often export Markdown escapes (\[ \] \. ...): the text must be read without
        line = prep(raw.rstrip())
        qm = QUOTE_LINE.match(line)
        lm = LIST_ITEM.match(line)
        if raw.lstrip().startswith("|"):
            flush_text()
            flush_quote()
            flush_list()
            table_lines.append(raw)
            continue
        flush_table()
        tk = TABLE_CLASS.match(line.strip())
        if tk and blocks and isinstance(blocks[-1], model.Table) and not blocks[-1].klass:
            blocks[-1].klass = tk.group(1)      # `{.name}` after the table: style from config table.classes.<name>
            if tk.group(1) not in cfg.get("table", {}).get("classes", {}):
                an.add(cid, "table class not defined in the style of volume.md (table.classes)", md_path.name, tk.group(1))
            continue
        cm = TABLE_CAPTION.match(line.strip())
        if cm and blocks and isinstance(blocks[-1], model.Table) and not blocks[-1].caption:
            text = cm.group(1).strip()
            num = f"Table {prefix}.{next(table_counter)}"
            for i in LABEL_ID.findall(" ".join(re.findall(r"\{[^}]*\}", text))):
                labels[i] = num
            text = re.sub(r"\s*\{[^}]*\}\s*$", "", text)
            blocks[-1].caption = f"{num}. {text}"
            continue
        if not line.strip():
            flush_par()
            flush_quote()          # an empty line closes the quotation (the list item stays open)
            continue
        if qm:
            flush_text()
            flush_list()
            quote.append(qm.group(1))
            continue
        flush_quote()
        if lm:
            flush_text()
            was_ordered = lm.group(2)[0].isdigit()
            if items and was_ordered != ordered:
                flush_list()
            ordered = was_ordered
            depth = len(lm.group(1).replace("\t", "    ")) // 2
            items.append((depth, lm.group(3).strip()))
            continue
        if items and line[:1] in " \t":      # continuation of a list item
            d, t = items[-1]
            items[-1] = (d, f"{t} {line.strip()}")
            continue
        flush_list()
        h = HEADING.match(line)
        img = IMAGE_LINE.match(line.strip())
        if h:
            flush_text()
            n = len(h.group(1))
            blocks.append(model.Heading(min(5, lvl + max(n - 1, 1)), h.group(2)))
        elif img:
            flush_text()
            ids = LABEL_ID.findall(" ".join(ANCHOR.findall(img.group(1))) + " " + (img.group(3) or ""))
            cap, name = ANCHOR.sub("", img.group(1)).strip(), img.group(2).strip()
            if re.match(r"(?i)^fig(?:ure|\.)?\s*\d", cap):
                an.add(cid, "caption already numbered (another label will be added)", md_path.name, cap[:40])
            p = find_image(name, search)
            if p is None:
                an.add(cid, "missing image", md_path.name, name)
                continue
            if front:                      # title-page image: without number nor caption
                a = parse_attrs(img.group(3))
                w_attr, h_attr = a.get("width"), a.get("height")
                if not (w_attr or h_attr):         # without measures: natural size (96 dpi), not enlarged
                    try:
                        from PIL import Image
                        with Image.open(p) as im:
                            w_attr = f"{im.size[0] * 2.54 / 96:.2f}cm"
                    except Exception:
                        pass
                blocks.append(model.Figure(p, "", width=w_attr, height=h_attr,
                                           align=a.get("align") or div_align or "center"))
                continue
            if not cap:
                an.add(cid, "empty caption", md_path.name, name)
            num = f"Fig. {prefix}.{next(fig_counter)}"
            for i in ids:
                labels[i] = num
            label = num + "."
            attrs = parse_attrs(img.group(3))
            pos = attrs.get("position") or attrs.get("pos")
            if pos and pos not in ("auto", "top", "bottom", "column", "left", "right"):
                an.add(cid, "invalid position attribute (auto|top|bottom|column|left|right)",
                       md_path.name, f"{name}: {pos}")
                pos = None
            klass = attrs.get("class") or attrs.get("role")      # `role=` is the historical name of `class=`
            if klass and klass not in icfg_classes:
                an.add(cid, "figure class not defined in the style of volume.md (images.classes)", md_path.name,
                       f"{name}: {klass}")
                klass = None
            blocks.append(model.Figure(p, f"{label} {cap}" if cap else label,
                                       klass=klass,
                                       width=attrs.get("width"), height=attrs.get("height"),
                                       position=pos, wrap=int(attrs["wrap"]) if attrs.get("wrap", "").isdigit() else 1,
                                       group=attrs.get("group")))
        else:
            cur.append(line.strip())
    if div is not None:
        an.add(cid, "unclosed ::: block", md_path.name, "the final ':::' line is missing")
        close_div()
    flush_table()
    flush_quote()
    flush_list()
    flush_text()
    for key in set(note_defs) - used_notes:
        an.add(cid, "footnote defined but never cited", md_path.name, f"[^{key}]")
    resolve_refs(blocks, labels, cid, md_path.name, an)
    blocks = group_end_figures(blocks, ch)
    raw = meta.get("authors") or meta.get("author") or ch.get("authors") or []
    if isinstance(raw, (str, dict)):
        raw = [raw]
    authors = [str(a.get("name", "")) if isinstance(a, dict) else str(a) for a in raw]
    return model.Chapter(cid, title, blocks, authors=[a for a in authors if a], new_page=bool(ch.get("new_page", True)), column_flow=int(ch.get("columns", 1)), bibliography=bool(ch.get("bibliography", True)) and not front, front=front,
                         running_title=str(meta.get("running_title") or ch.get("running_title") or ""))
