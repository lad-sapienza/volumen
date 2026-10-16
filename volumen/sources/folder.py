"""Sorgente 'folder' (`source=<cartella>` nella nota del volume): una cartella di file Markdown, un file per voce -> Chapter.

I file si riuniscono in un unico testo (titoli spostati di un livello) che passa dal lettore
Markdown dei capitoli: stesse tabelle, figure, note e link. Qui si sceglie solo quali file entrano
e in che ordine (prefissi, eccezioni) e si adattano i blocchi (a-capo di pagina, colonne, ancore per
i link [ID](ID.md))."""
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
    """-> il piu' lungo dei prefissi `tokens` (series_order / exclude_prefixes) che precede l'ID, None se nessuno.
    Dopo una lettera non deve seguirne un'altra: "S" vale per S1-01, non per SA-01."""
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
    """-> {id: (percorso, meta, corpo)} per tutti i .md della cartella. ID = campo `id_field` del front matter
    (se dato e presente), altrimenti il nome del file senza .md."""
    out = {}
    for f in sorted(folder.glob("*.md")):
        meta, body = markdown.split_frontmatter(f.read_text(encoding="utf-8"))
        cid = str(meta.get(id_field) or f.stem) if id_field else f.stem
        out[cid] = (f, meta, body)
    return out


def card_ids(ch, base_dir):
    """Voci incluse nel volume (nome file senza .md): servono ai link [testo](ID.md) dagli altri capitoli.
    Una voce esclusa non ha destinazione: il link e' segnalato come non risolto."""
    d = cards_dir(ch, base_dir)
    if not d.is_dir():
        return {}
    chosen, _ = select_cards(read_cards(d, ch.get("id_field")), ch)
    return {c: c for c in chosen}


def select_cards(cards, ch):
    """Filtra e ordina secondo volume.md: series_order (prefissi inclusi, nell'ordine), exclude_prefixes,
    poi le eccezioni `include` / `exclude` / `first` (liste di ID). -> (incluse, [(id, motivo)])."""
    order = ch.get("series_order", [])
    excl = set(ch.get("exclude_prefixes", []))
    tokens = list(order) + list(excl)
    by_series = "series_order" in ch        # senza series_order: nessun filtro per serie, ordine naturale
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
    """Titoli spostati di un livello (# ID -> ## ID: il capitolo ha il suo titolo) e immagini con
    percorso assoluto (relativi alla scheda, non al capitolo)."""
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
    """Capitolo 'folder' -> (Chapter, n_voci, esclusi)."""
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
    chapter.column_flow = 1                      # le colonne valgono per il solo testo delle voci
    return chapter, len(chosen), excluded
