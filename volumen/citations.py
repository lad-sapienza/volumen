"""Citazioni bibliografiche stile Pandoc (`[@chiave, 49]`, `@chiave`) risolte con `pandoc --citeproc`.

Tutte le citazioni del volume passano da UNA sola esecuzione di pandoc: cosi' la
disambiguazione autore-data (2020a/2020b) e' coerente in tutto il volume. Ogni capitolo riceve
poi la propria bibliografia (solo le opere che cita), gia' formattata dallo stile CSL."""
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from . import model

KEY = r"[\w](?:[\w:.\-]*[\w])?"
BRACKET = re.compile(r"\[(?:[^\[\]]*?)(?<![\w])-?@" + KEY + r"[^\[\]]*\]")      # [@a, 30; @b]
BARE = re.compile(r"(?<![\w@/\[\\])@(" + KEY + ")")                            # @chiave (narrativa)
KEYS_IN = re.compile(r"(?<![\w])-?@(" + KEY + ")")
URL = re.compile(r"https?://[^\s)\]>]+")
UNESC = re.compile(r"\\([\\`{}\[\]()#+.!|<>~^$_*'\"@-])")


def clusters_in(text):
    """Citazioni presenti in un testo: prima le forme fra parentesi quadre, poi le narrative."""
    found = [m.group(0) for m in BRACKET.finditer(text)]
    rest = BRACKET.sub(" ", text)
    found += [m.group(0) for m in BARE.finditer(rest)]
    return found


SEPARATOR_TYPO = re.compile(r",\s*(?=-?@)")   # `, @chiave`: pandoc vuole `;` fra due citazioni


def replace_clusters(text, table):
    def sub_bracket(m):
        return table.get(m.group(0), m.group(0))
    text = BRACKET.sub(sub_bracket, text)
    return BARE.sub(lambda m: table.get(m.group(0), m.group(0)), text)


def _break_urls(s):
    """Permette l'a-capo negli URL lunghi (spazio di larghezza zero dopo / . - _ ?)."""
    return URL.sub(lambda m: re.sub(r"([/.\-_?&=])", "\\1\u200b", m.group(0)), s)


def _clean(md):
    """Testo restituito da pandoc (markdown) -> testo per i renderer."""
    md = re.sub(r"<(https?://[^>\s]+)>", r"\1", md)              # <url> -> url
    md = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)", r"\1", md)    # [testo](url) -> testo
    md = UNESC.sub(r"\1", md)
    return _break_urls(" ".join(md.split()))


def process(volume, bib_path, csl_path, an, lang="en-US", title="References"):
    """Sostituisce le citazioni nei testi e aggiunge a ogni capitolo la sua bibliografia."""
    if not shutil.which("pandoc"):
        sys.exit("pandoc non trovato: serve per le citazioni bibliografiche (brew install pandoc).")
    bib_path = Path(bib_path)
    if not bib_path.exists():
        sys.exit(f"File bibliografico non trovato: {bib_path}")

    # 1. citazioni per capitolo
    per_chapter = []                 # [(chapter, set(cluster))]
    all_clusters = {}                # cluster -> indice
    for ch in volume.chapters:
        found = set()

        def grab(t):
            if t:
                found.update(clusters_in(t))
            return t
        model.map_text(ch.blocks, grab)
        per_chapter.append((ch, found))
        for c in sorted(found):
            all_clusters.setdefault(c, len(all_clusters))
    if not all_clusters:
        return

    # 2. un solo documento pandoc: un paragrafo per citazione
    ordered = sorted(all_clusters, key=all_clusters.get)
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "cit.md"
        src.write_text("\n\n".join(ordered) + "\n\n::: {#refs}\n:::\n",
                       encoding="utf-8")
        cmd = ["pandoc", str(src), "--citeproc", "--bibliography", str(bib_path),
               "-t", "markdown-smart", "--wrap=none", "-M", f"lang={lang}",
               "-M", "link-citations=false"]
        if csl_path:
            cmd += ["--csl", str(csl_path)]
        r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"pandoc --citeproc e' fallito:\n{r.stderr[:1500]}")

    # 3. chiavi mancanti (segnalate) e output
    missing = set(re.findall(r"citation (\S+) not found", r.stderr))
    m_refs = re.search(r"^:{3,} \{#refs", r.stdout, re.M)
    body, refs = (r.stdout[:m_refs.start()], r.stdout[m_refs.start():]) if m_refs else (r.stdout, "")
    formatted = [p.strip() for p in re.split(r"\n\s*\n", body.strip()) if p.strip()]
    if len(formatted) != len(ordered):
        sys.exit(f"Citazioni: attese {len(ordered)} risposte da pandoc, ricevute {len(formatted)}.")
    table = {c: _clean(f) for c, f in zip(ordered, formatted)}
    entries = {}
    order = []
    for m in re.finditer(r"::: \{#ref-(.+?) [^}]*\}\n(.*?)\n:::", refs, re.S):
        entries[m.group(1)] = _clean(m.group(2))
        order.append(m.group(1))

    # 4. sostituzione nei testi + bibliografia per capitolo
    for ch, found in per_chapter:
        if not found:
            continue
        model.map_text(ch.blocks, lambda t: replace_clusters(t, table) if t else t)
        keys = set()
        for c in found:
            keys.update(KEYS_IN.findall(c))
        for c in sorted(found):
            if c.startswith("[") and SEPARATOR_TYPO.search(c):
                # non si corregge: il testo resta com'e' e pandoc lo interpreta a suo modo
                an.add(ch.id, "citazione: ',' prima di @chiave (fra le opere serve ';'; pandoc "
                       "ignora le altre citazioni)", "bibliografia", c[:70] + "…")
        for k in sorted(keys & missing):
            an.add(ch.id, "citazione: chiave non presente nel .bib", "bibliografia", k)
        if getattr(ch, "bibliography", True):
            mine = [(k, entries[k]) for k in order if k in keys]
            if mine:
                lvl = next((b.level for b in ch.blocks if isinstance(b, model.Heading)), 1) + 1
                ch.blocks.append(model.Bibliography(title, lvl, mine))
