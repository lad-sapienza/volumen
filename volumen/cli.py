"""Punto d'ingresso unico: composizione e stile (volume.md) -> PDF (Typst) / DOCX."""
import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

from . import citations, model, shrink
from .config import HERE, load_config
from .render import docx as render_docx
from .render import typst as render_typst
from .reports import Anomalies, write_reports
from .volume_note import load_volume_note
from .sources import folder, markdown, resolve_path

DESCRIPTION = """\
Volumen by LAD: typesets a volume from Markdown notes. The engine only does the layout: it never
corrects data, it reports problems in anomalies.md / anomalies.csv.

Formats:
  typst   PDF via Typst (--keep-typ: also keep the .typ; --no-pdf: only the .typ)   [default]
  docx    DOCX (python-docx)

Usage:
  python3 -m volumen                          # PDF with Typst
  python3 -m volumen --format docx            # DOCX
  python3 -m volumen --only F1-01 F5-07       # only some entries of the folders (tests)
  python3 -m volumen --set styles.normal.size=10.5 --set page.margin_interior=3
"""


def load_volume(path):
    if not path.exists():
        sys.exit(f"Volume note not found: {path}")
    if path.suffix.lower() != ".md":
        sys.exit(f"The composition of the volume is a Markdown note (volume.md), not {path.name}: see the README.")
    return load_volume_note(path)


def find_volume(args):
    """Dove stanno i contenuti: --volume, poi VOLUMEN_NOTE, poi il file `.volume` del progetto (una riga: il percorso,
    ignorato da git), poi volume.md nella cartella corrente."""
    marker = HERE / ".volume"
    wanted = (args.volume or os.environ.get("VOLUMEN_NOTE")
              or (marker.read_text(encoding="utf-8").strip() if marker.exists() else None)
              or Path.cwd() / "volume.md")
    path = Path(wanted).expanduser()
    return path if path.is_absolute() else Path.cwd() / path


def load_project(args):
    """-> (cfg, percorso di volume.md, contenuto, cartella di volume.md). Lo stile viene dai blocchi yaml della nota;
    le anomalie della composizione stanno in vol['_anomalie']."""
    vol_path = find_volume(args)
    vol, warnings = load_volume(vol_path)
    vol["_anomalie"] = warnings
    cfg = load_config(args, vol.pop("_config", {}))
    return cfg, vol_path, vol, vol_path.resolve().parent


def output_dir(args, vol, base_dir):
    """Cartella di output: --out (relativa alla cartella corrente), poi `output_dir` della nota (relativa alla nota),
    poi out/ accanto alla nota."""
    if args.out:
        out_dir = Path(args.out).expanduser()
        return out_dir if out_dir.is_absolute() else Path.cwd() / out_dir
    out_dir = Path(vol.get("output", {}).get("dir", "out")).expanduser()
    return out_dir if out_dir.is_absolute() else base_dir / out_dir


def main(argv=None, default_format="typst"):
    if argv is None:
        argv = sys.argv[1:]
    ap = argparse.ArgumentParser(description=DESCRIPTION,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--volume", help="volume note .md (default: VOLUMEN_NOTE, then the project's .volume file, then ./volume.md)")
    ap.add_argument("--config", help="JSON/YAML file of graphics/layout to overlay on the note's style (optional)")
    ap.add_argument("--out", help="output folder (default: the note's `output_dir`, then out/ next to the note)")
    ap.add_argument("--open", action="store_true", help="open the produced file when finished (PDF if present, otherwise DOCX/.typ)")
    ap.add_argument("--name", help="output file name (without extension)")
    ap.add_argument("--set", action="append", metavar="KEY=VALUE",
                    help="inline override of the style, e.g. styles.h2.size=15 (repeatable)")
    ap.add_argument("--format", choices=["typst", "docx", "pdf", "both"], default=default_format,
                    help="typst (PDF, default) | docx")
    ap.add_argument("--keep-typ", action="store_true", help="with --format typst: also keep the .typ (debug)")
    ap.add_argument("--no-pdf", action="store_true", help="with --format typst: only the .typ")
    ap.add_argument("--shrink", nargs="?", const="screen", choices=shrink.PRESETS, metavar="PRESET",
                    help="besides the PDF, writes <name>-shrink.pdf reduced with Ghostscript (drafts); "
                         "PRESET: screen (default, 72 dpi), ebook (150), printer (300)")
    ap.add_argument("--annotations", action="store_true",
                    help="builds the CriticMarkup annotations ({==text==}{>>comment<<}): Word comments / "
                         "PDF annotations (drafts only; without the flag they are left out)")
    ap.add_argument("--only", nargs="+", metavar="ID", help="only these entries of the `source: folder` chapters (tests)")
    ap.add_argument("--chapter", nargs="+", metavar="ID",
                    help="typeset only these chapters (ids from the volume note; a container includes its "
                         "children), e.g. --chapter 4 or --chapter 6.1 6.2")
    ap.add_argument("--list-chapters", action="store_true", help="list the chapter ids and exit")
    ap.add_argument("--validate", action="store_true",
                    help="check the volume without typesetting: missing files and links, images, citations; writes anomalies.md/.csv")
    ap.add_argument("--json", action="store_true",
                    help="for programs (Obsidian plugin): stdout carries only a JSON object (result, files written, "
                         "anomaly counts; with --list-chapters the chapter list), everything else goes to stderr")
    args = ap.parse_args(argv)
    json_out = None
    if args.json:                 # stdout riservato al JSON: anche l'output dei programmi figli (typst) va su stderr
        json_out = os.fdopen(os.dup(1), "w", encoding="utf-8")
        os.dup2(2, 1)
        sys.stdout = sys.stderr
    if args.format in ("pdf", "both"):
        sys.exit("--format pdf/both (PDF via LibreOffice) is no longer supported: use the default `typst` for PDF "
                 "or `--format docx` for DOCX only.")

    cfg, vol_path, vol, base_dir = load_project(args)
    acfg = cfg.get("annotations", {})
    model.ANNOT.update(enabled=bool(args.annotations or acfg.get("enabled")),
                       author=acfg.get("author", "Author"), initials=acfg.get("initials", ""),
                       color=acfg.get("color", model.ANNOT["color"]), items=[],
                       suggestions="reject" if acfg.get("suggestions") == "reject" else "accept")
    out_dir = output_dir(args, vol, base_dir)
    out_name = args.name or vol.get("output", {}).get("name", "volume")

    if args.list_chapters:
        rows = []

        def show(chs, depth=0):
            for c in chs:
                title = c.get("title", "")
                if not title and c.get("file") and Path(c["file"]).is_file():     # il titolo e' quello del file
                    title = markdown.split_frontmatter(Path(c["file"]).read_text(encoding="utf-8"))[0].get("title", "")
                kind = c.get("source", "contenitore")
                rows.append({"id": str(c.get("id", "?")), "title": title, "source": kind, "depth": depth,
                             "file": c.get("file"), "dir": c.get("dir")})
                if not json_out:
                    print(f"{'  ' * depth}{c.get('id', '?'):<8} {title}  [{kind}]")
                show(c.get("chapters", []), depth + 1)
        show(vol.get("chapters", []))
        if json_out:
            json.dump({"volume": str(vol_path), "chapters": rows}, json_out, ensure_ascii=False)
            json_out.write("\n")
            json_out.flush()
        return

    wanted = {str(x) for x in (args.chapter or [])}
    known = set()

    def collect_ids(chs):
        for c in chs:
            known.add(str(c.get("id", "")))
            collect_ids(c.get("chapters", []))
    collect_ids(vol.get("chapters", []))
    if wanted - known:
        sys.exit(f"Chapter(s) not found in volume.md: {', '.join(sorted(wanted - known))} "
                 f"(see --list-chapters)")
    if wanted and not args.name:
        out_name = f"{out_name}-" + "_".join(sorted(wanted)).replace(".", "-")

    chapter_ids = {}                  # nome file (senza .md) -> id, per i link [[nome-file]]

    def collect_files(chs):
        for c in chs:
            if c.get("file"):
                chapter_ids[Path(str(c["file"])).stem] = str(c.get("id", ""))
            if c.get("source") == "folder":      # link [testo](F1-01.md): una voce per file
                chapter_ids.update(folder.card_ids({"sources": vol.get("sources", {}), **c}, base_dir))
            collect_files(c.get("chapters", []))
    collect_files(vol.get("chapters", []))

    an = Anomalies()
    for row in vol.get("_anomalie", []):
        an.add(*row)
    an_hidden = Anomalies()           # anomalie dei capitoli caricati solo per le citazioni (non impaginati)
    chapters, n_included, excluded = [], 0, []
    hidden = []                       # capitoli Markdown non selezionati (servono alle citazioni)
    has_bib = bool(vol.get("sources", {}).get("bibliography"))

    auto_number = bool(cfg.get("chapter_numbering", True))

    def number_label(ch, title):
        """Numero da anteporre al titolo ("6." per i capitoli, "6.1" per i sotto-capitoli), oppure
        "" se la numerazione e' disattivata (config `chapter_numbering`, per capitolo `numbered: false`),
        manca l'id o il titolo e' gia' numerato a mano."""
        cid = str(ch.get("id", "")).strip()
        if not (auto_number and ch.get("numbered", True) and re.fullmatch(r"\d+(\.\d+)*", cid) and title):
            return ""        # id non numerico ({id=preface}): fuori dalla numerazione
        if title.startswith(cid) and not title[len(cid):len(cid) + 1].isalnum():
            return ""
        return cid + ("." if "." not in cid else "")

    def number_chapter(chapter, ch):
        old = chapter.title
        label = number_label(ch, old)
        if not label:
            return chapter
        chapter.title = f"{label} {old}"
        first = chapter.blocks[0] if chapter.blocks else None
        if isinstance(first, (model.Heading, model.PartTitle)) and first.text == old:
            first.text = chapter.title
        return chapter

    def load(ch, level, inherited=False):
        """Carica un capitolo (o un contenitore con figli); level = livello base dei titoli;
        inherited = un contenitore antenato e' stato scelto con --chapter (include i figli)."""
        nonlocal n_included
        ch = {"sources": vol.get("sources", {}), "chapter_level": level, "chapter_ids": chapter_ids, **ch}
        kind = ch.get("source")
        chosen = not wanted or inherited or str(ch.get("id", "")) in wanted
        if ch.get("chapters") and ch.get("title"):
            label = number_label(ch, str(ch["title"]))
            ch = {**ch, "title": f"{label} {ch['title']}" if label else ch["title"]}
        if ch.get("chapters"):                       # contenitore
            lvl = ch.get("base_level", level)
            if not chosen:
                pass
            elif ch.get("divider"):
                chapters.append(model.Chapter(str(ch.get("id", "")), ch.get("title", ""),
                                              [model.PartTitle(lvl, ch.get("title", ""))]))
            elif ch.get("title"):
                chapters.append(model.Chapter(str(ch.get("id", "")), ch["title"],
                                              [model.Heading(lvl, ch["title"])]))
            for sub in ch["chapters"]:
                load(sub, lvl + 1, inherited or chosen and bool(wanted))
        elif not chosen and kind == "markdown" and has_bib:
            hidden.append(markdown.load_chapter(cfg, ch, base_dir, an_hidden))
        elif not chosen:
            return                                   # non selezionato: non si carica (piu' veloce)
        elif kind == "folder":
            chapter, n, exc = folder.load_chapter(cfg, ch, base_dir, an, only=args.only)
            n_included += n
            excluded.extend(exc)
            chapters.append(number_chapter(chapter, ch))
        elif kind == "markdown":
            chapters.append(number_chapter(markdown.load_chapter(cfg, ch, base_dir, an), ch))
        else:
            sys.exit(f"unsupported source: {kind!r} (chapter {ch.get('id')!r})")

    for ch in vol.get("chapters", []):
        load(ch, 1)

    # frontmatter (frontespizio, colophon, ...): file Markdown prima dell'indice; non con --chapter
    front = []
    if not wanted:
        vars_ = {k: v for k, v in vol.items() if isinstance(v, (str, int, float))}
        vars_["authors"] = ", ".join(str(a.get("name", "")) if isinstance(a, dict) else str(a)
                                     for a in vol.get("authors") or [])
        for k, name in enumerate(vol.get("frontmatter") or []):
            fch = {"sources": vol.get("sources", {}), "chapter_level": 1, "chapter_ids": chapter_ids,
                   "id": f"front{k + 1}", "file": name, "front": True, "pages": True, "vars": vars_}
            front.append(markdown.load_chapter(cfg, fch, base_dir, an))

    bib = vol.get("sources", {}).get("bibliography")
    if bib:
        # con --chapter le citazioni si risolvono su TUTTO il volume (le lettere 2020a/2020b e la
        # bibliografia restano identiche a quelle del volume completo); le anomalie solo dei selezionati
        an_cit = Anomalies() if wanted else an
        citations.process(model.Volume(meta={}, chapters=chapters + hidden),
                          resolve_path(bib, {"sources": vol.get("sources", {})}, base_dir),
                          resolve_path(vol["sources"]["csl"], {"sources": vol["sources"]}, base_dir)
                          if vol["sources"].get("csl") else None,
                          an_cit, lang=vol.get("lang", "en-US"),
                          title=vol.get("bibliography_title", "References"))
        if wanted:
            keep = {c.id for c in chapters}
            for row in an_cit.rows:
                if row[0] in keep:
                    an.add(*row)

    volume = model.Volume(meta={k: vol.get(k) for k in ("title", "authors", "toc", "list_of_figures")},
                          chapters=chapters, front=front)

    if args.validate:
        write_reports(an, excluded, out_dir, {"n_included": n_included})
        print(f"Check: {n_included} entries, {len(excluded)} excluded, {len(an.rows)} anomalies")
        for k, n in an.counts().most_common():
            print(f"  {n:4d}  {k}")
        if json_out:
            json.dump({"ok": True, "validate": True, "volume": str(vol_path), "output_dir": str(out_dir),
                       "anomalies": str(out_dir / "anomalies.md"), "counts": dict(an.counts()),
                       "n_included": n_included, "n_excluded": len(excluded)}, json_out, ensure_ascii=False)
            json_out.write("\n")
            json_out.flush()
        return

    written = []
    if args.format == "typst":
        source = render_typst.build_source(cfg, volume)
        written += render_typst.write_and_compile(source, out_dir, out_name,
                                                  compile_pdf=not args.no_pdf,
                                                  keep_typ=args.keep_typ)
    else:
        doc = render_docx.build_document(cfg, volume, an)
        out_dir.mkdir(parents=True, exist_ok=True)
        docx_path = out_dir / f"{out_name}.docx"
        doc.save(docx_path)
        written.append(docx_path)
    if args.shrink:
        for pdf in [p for p in written if p.suffix == ".pdf"]:
            small = shrink.shrink_pdf(pdf, preset=args.shrink)
            print(f"Reduced: {pdf.name} {shrink.mb(pdf):.1f} MB -> {small.name} {shrink.mb(small):.1f} MB")
            written.append(small)
    write_reports(an, excluded, out_dir, {"n_included": n_included})
    written += [out_dir / "anomalies.md", out_dir / "anomalies.csv"]

    print(f"Entries typeset: {n_included}  ·  excluded: {len(excluded)}")
    for k, n in an.counts().most_common():
        print(f"  {n:4d}  {k}")
    print("Written:", ", ".join(str(p) for p in written))
    if json_out:
        json.dump({"ok": True, "volume": str(vol_path), "output_dir": str(out_dir), "written": [str(p) for p in written],
                   "pdf": next((str(p) for p in written if p.suffix == ".pdf" and not p.stem.endswith("-shrink")), None),
                   "docx": next((str(p) for p in written if p.suffix == ".docx"), None),
                   "typ": next((str(p) for p in written if p.suffix == ".typ"), None),
                   "anomalies": str(out_dir / "anomalies.md"), "counts": dict(an.counts()),
                   "n_included": n_included, "n_excluded": len(excluded)}, json_out, ensure_ascii=False)
        json_out.write("\n")
        json_out.flush()
    if args.open:
        docs = [p for p in written if p.suffix in (".pdf", ".docx", ".typ") and not p.stem.endswith("-shrink")]
        target = next((p for p in docs if p.suffix == ".pdf"), docs[0] if docs else None)
        if target:
            subprocess.run(["open", str(target)], check=False)
