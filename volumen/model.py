"""Modello intermedio del volume: cio' che i sorgenti producono e i renderer consumano."""
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# Nota a pie di pagina inline: la sorgente sostituisce [^n] con NOTE_OPEN + testo della nota + NOTE_CLOSE;
# i renderer la trasformano in una vera nota (Typst #footnote, Word footnotes.xml).
NOTE_OPEN, NOTE_CLOSE = "\x03", "\x04"
NOTE = re.compile(f"{NOTE_OPEN}(.*?){NOTE_CLOSE}", re.S)
# Link a un altro capitolo: LINK_OPEN + id capitolo + "|" + testo + LINK_CLOSE (cliccabile, senza cambiare la resa)
LINK_OPEN, LINK_CLOSE = "\x05", "\x06"
CHLINK = re.compile(f"{LINK_OPEN}([^|{LINK_CLOSE}]*)\\|(.*?){LINK_CLOSE}", re.S)


def strip_chapter_links(text):
    """Toglie i marcatori dei link tra capitoli lasciando il testo (dove il link non e' supportato)."""
    return CHLINK.sub(lambda m: m.group(2), text) if isinstance(text, str) and LINK_OPEN in text else text


def chapter_anchor(cid):
    """Nome di etichetta/segnalibro del capitolo: solo lettere, cifre e '_' (valido in Typst e Word)."""
    return "ch_" + re.sub(r"\W", "_", str(cid))

# grassetto/corsivo: il corsivo con _ solo ai bordi di parola (non dentro URL o nomi_con_underscore)
# barrato: ~~testo~~
# evidenziato: ==testo== (Obsidian/Pandoc mark) oppure [testo]{.mark} (span Pandoc)
# annotazioni (CriticMarkup): {==testo==}{>>commento<<} su un passo, {>>commento<<} puntuale
INLINE_MD = re.compile(r"(\{\+\+[^\n]*?\+\+\}|\{--[^\n]*?--\}|\{~~[^\n]*?~>[^\n]*?~~\}|\{==[^\n]*?==\}\{(?:[A-Za-z_]+=\"[^\"\n]*\"\s*)*>>[^\n]*?<<\}|\{(?:[A-Za-z_]+=\"[^\"\n]*\"\s*)*>>[^\n]*?<<\}|~~[^~\n]+~~|==(?!=)(?:[^=\n]|=(?!=))+==|\[[^\]\n]+\]\{\.mark\}|\*\*[^*]+\*\*|\^[^^\s]+\^|\*[^*]+\*|(?<![\w\\])_[^_]+_(?!\w))")


@dataclass
class Heading:
    level: int                    # 1..5, corrisponde agli stili h1..h5
    text: str
    page_break_before: bool = False
    anchor: Optional[str] = None  # id di un link interno (es. scheda di un complesso): [testo](ID.md)


@dataclass
class Text:
    """Paragrafi separati da riga vuota; a-capo singoli = line break; markup inline **/*/_."""
    text: str
    columns: int = 1              # >1: testo a colonne (solo dove il renderer lo supporta)


@dataclass
class StyledText:
    """Uno o piu' paragrafi (separati da riga vuota) con stile personalizzato (`::: {attributi}`).
    style: dizionario risolto da styled.resolve (font, size, bold, align, space_before, ...)."""
    text: str
    style: dict


@dataclass
class PageBreak:
    """Nuova pagina (riga `---` nei file di frontmatter)."""


@dataclass
class Figure:
    path: Path
    caption: str                  # gia' completa e numerata ("Fig. 6.3.1. ...")
    klass: Optional[str] = None   # classe di figura (`{class=plan}`): misure e spazi da config images.classes.<klass>
    width: Optional[str] = None   # "12cm", "60%", "3in" ... (% della larghezza disponibile)
    height: Optional[str] = None
    position: Optional[str] = None   # auto | top | bottom | column | left | right (solo Typst a colonne)
    wrap: int = 1                 # con position left/right: quanti paragrafi seguenti girano intorno
    group: Optional[str] = None   # 'end': figura di fine sezione (le consecutive diventano una FigureGroup)
    align: Optional[str] = None   # left | center | right (immagini di frontmatter; default: centro)


@dataclass
class FigureGroup:
    """Figure di fine capitolo/sezione. Con title: sezione dedicata (pagina di titolo)."""
    figures: list
    title: Optional[str] = None


@dataclass
class Table:
    """Tabella generica (es. da Markdown): intestazione + righe; celle con markup inline.
    ratios = pesi relativi delle colonne (None = uguali); aligns = 'left'|'center'|'right' per colonna."""
    header: list
    rows: list
    ratios: Optional[list] = None
    aligns: Optional[list] = None
    caption: str = ""             # numerata, sopra la tabella
    klass: Optional[str] = None   # classe di tabella (riga `{.nome}` dopo la tabella): config table.classes.<nome>


@dataclass
class Quote:
    """Citazione (blockquote); source = riferimento su riga a parte, dopo il trattino lungo."""
    text: str
    source: Optional[str] = None


@dataclass
class ListBlock:
    items: list                   # [(profondita', testo)], profondita' 0 = primo livello
    ordered: bool = False


@dataclass
class PartTitle:
    """Pagina isolata con il solo titolo, centrato (contenitore di capitoli)."""
    level: int
    text: str


@dataclass
class Chapter:
    id: str
    title: str
    blocks: list = field(default_factory=list)
    new_page: bool = True         # il capitolo inizia su pagina nuova
    running_title: str = ""       # testo dell'intestazione corrente (default: title)
    authors: list = field(default_factory=list)   # autori del capitolo (riga grigia sotto il titolo h1)
    bibliography: bool = True     # aggiunge la bibliografia delle opere citate in fondo al capitolo
    column_flow: int = 1          # >1: dopo il titolo, tutto il capitolo in un unico flusso a colonne
    front: bool = False           # frontespizio/colophon: senza titolo, intestazione e numero di pagina


@dataclass
class Volume:
    meta: dict
    chapters: list
    front: list = field(default_factory=list)    # frontmatter (Chapter con front=True), prima dell'indice


@dataclass
class Bibliography:
    """Riferimenti bibliografici citati nel capitolo (gia' formattati dallo stile CSL)."""
    title: str
    level: int
    entries: list                 # [(chiave, testo con markup inline *corsivo*)]


def map_text(blocks, fn):
    """Applica fn a ogni testo dei blocchi (paragrafi, citazioni, elenchi, tabelle, didascalie,
    titoli). fn(str) -> str."""
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
    """'12cm', '5in', '300px', '60%' (di ref_cm) -> cm; None se vuoto o non valido."""
    if not spec:
        return None
    m = re.fullmatch(r"\s*([0-9]*\.?[0-9]+)\s*(cm|mm|in|pt|px|%)?\s*", str(spec))
    if not m:
        return None
    v, unit = float(m.group(1)), m.group(2) or "cm"
    return ref_cm * v / 100 if unit == "%" else v * _UNITS[unit]


MARK = re.compile(r"^(?:==(.+)==|\[(.+)\]\{\.mark\})$", re.S)


def mark_text(part):
    """Se `part` e' un evidenziato (==t== / [t]{.mark}) -> il testo interno, altrimenti None."""
    m = MARK.match(part)
    return (m.group(1) or m.group(2)) if m else None


CRITIC = re.compile(r"^(?:\{==(.*?)==\}\{(?:[A-Za-z_]+=\"[^\"\n]*\"\s*)*>>(.*?)<<\}|\{(?:[A-Za-z_]+=\"[^\"\n]*\"\s*)*>>(.*?)<<\})$", re.S)

# stato delle annotazioni (impostato dal CLI: --annotations o config `annotations`)
ANNOT = {"enabled": False, "author": "", "initials": "", "color": "FFD54F", "items": [],
         "suggestions": "accept"}     # senza --annotations i suggerimenti {++ ++} {-- --} {~~ ~> ~~}: "accept" | "reject"

CRITIC_EDIT = re.compile(r"^(?:\{\+\+(.*?)\+\+\}|\{--(.*?)--\}|\{~~(.*?)~>(.*?)~~\})$", re.S)


def critic_edit(part):
    """Se `part` e' un suggerimento CriticMarkup -> (testo vecchio, testo nuovo), altrimenti None:
    {++nuovo++} -> ("", nuovo); {--vecchio--} -> (vecchio, ""); {~~vecchio~>nuovo~~} -> (vecchio, nuovo)."""
    m = CRITIC_EDIT.match(part)
    if not m:
        return None
    if m.group(1) is not None:
        return "", m.group(1)
    if m.group(2) is not None:
        return m.group(2), ""
    return m.group(3), m.group(4)


def accepted_edit(old, new):
    """Testo che resta senza --annotations (annotations.suggestions: accept = nuovo, reject = vecchio)."""
    return old if ANNOT["suggestions"] == "reject" else new


def critic_parts(part):
    """Se `part` e' un'annotazione CriticMarkup -> (testo annotato o "", commento), altrimenti None."""
    m = CRITIC.match(part)
    if not m:
        return None
    return (m.group(1) or "", (m.group(2) if m.group(1) is not None else m.group(3)) or "")


def annotation_tag(n):
    """Marcatore invisibile (solo ASCII) che il PDF porta per ritrovare dove ancorare l'annotazione."""
    return f"ZQA{n:04d}QZ"


def running_left(chapter, volume, hcfg):
    """Testo dell'intestazione delle pagine pari (sinistre): header.left_pages = "author" (default:
    autori del capitolo, altrimenti quelli del volume) oppure "title" (come le pagine destre)."""
    if hcfg.get("left_pages", "author") != "author":
        return None
    names = list(chapter.authors) or [
        str(a.get("name", "")) if isinstance(a, dict) else str(a)
        for a in (volume.meta.get("authors") or [])]
    return ", ".join(n for n in names if n)
