"""Renderer Typst: consuma i blocchi del modello e compila con `typst compile`."""
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image

from .. import model
from ..config import heading_style, style_cfg

HERE = Path(__file__).resolve().parent

# left/right/center: mappatura diretta; justify e' un booleano a parte in Typst
# (par.justify), qui l'allineamento "di base" (es. dell'ultima riga) e' left,
# come in Word.
ALIGN_TYPST = {"left": "left", "right": "right", "center": "center", "justify": "left"}


def leading_pt(sc):
    """line_height e' il passo fra le righe in pt (in Word: interlinea
    "esatta"). Il riquadro di riga e' impostato a 1em (top-edge 0.75em,
    bottom-edge 0.25em sotto la linea di base), quindi il leading e' la
    differenza: risultato indipendente dai metrici del font."""
    return round(sc["line_height"] - sc["size"], 2)


def typst_align(align_value):
    return ALIGN_TYPST.get(align_value, "left")


def typst_color(hex_color):
    return f'rgb("#{hex_color}")'


# --------------------------------------------------------------------------
# Escape e markdown -> Typst
# --------------------------------------------------------------------------
def esc(text):
    """Escapa i caratteri speciali di Typst in un frammento di testo semplice."""
    text = re.sub(r"[\\#\[\]<>@$`_*~]", lambda m: "\\" + m.group(0), text)
    text = text.replace("//", "\\/\\/")   # '//' aprirebbe un commento (es. negli URL)
    # a inizio testo "1. ", "- ", "+ ", "= " sono elenco/titolo (es. "1. Preface": enum dentro un par)
    return re.sub(r"^(?:(\d+)(?=\.)|([=+/-]))", lambda m: m.group(1) + "\\" if m.group(1) else "\\" + m.group(2), text)


def esc_str(text):
    """Escapa una stringa da mettere tra virgolette Typst, es. image("...")."""
    return text.replace("\\", "\\\\").replace('"', '\\"')


HIGHLIGHT = "FFEB3B"      # colore evidenziato (typography.highlight_color)
LINKS = {}                # stile dei link (config `links`: color, underline, bold); vuoto = come il testo


def link_style_wrap(markup):
    """Stile dei link da config `links` (color, underline, bold); senza chiavi, nessun cambiamento."""
    if LINKS.get("bold"):
        markup = f"#strong[{markup}]"
    if LINKS.get("underline"):
        markup = f"#underline[{markup}]"
    if LINKS.get("color"):
        markup = f'#text(fill: {typst_color(LINKS["color"])})[{markup}]'
    return markup


def md_inline_to_typst(line):
    """**bold** -> *bold*, *it*/_it_ -> _it_ (sintassi Typst), resto escapato; le note inline
    diventano #footnote[...]."""
    if model.NOTE_OPEN in line:
        pieces, pos = [], 0
        for m in model.NOTE.finditer(line):
            pieces.append(md_inline_to_typst(line[pos:m.start()]))
            pieces.append("#footnote[" + md_inline_to_typst(m.group(1)) + "]")
            pos = m.end()
        pieces.append(md_inline_to_typst(line[pos:]))
        return "".join(pieces)
    if model.LINK_OPEN in line:
        # link a un altro capitolo: cliccabile, stessa resa del testo (se il capitolo non ha
        # l'ancora, resta testo semplice: chlink in preambolo)
        pieces, pos = [], 0
        for m in model.CHLINK.finditer(line):
            pieces.append(md_inline_to_typst(line[pos:m.start()]))
            pieces.append(f'#chlink("{model.chapter_anchor(m.group(1))}")[' + link_style_wrap(md_inline_to_typst(m.group(2))) + "]")
            pos = m.end()
        pieces.append(md_inline_to_typst(line[pos:]))
        return "".join(pieces)
    out = []
    for part in model.INLINE_MD.split(line):
        if not part:
            continue
        if model.critic_parts(part) is not None:
            text, comment = model.critic_parts(part)
            inner = md_inline_to_typst(text) if text else ""
            if model.ANNOT["enabled"]:
                n = len(model.ANNOT["items"]) + 1
                model.ANNOT["items"].append({"tag": model.annotation_tag(n), "text": text, "comment": comment})
                if inner:
                    inner = f'#highlight(fill: rgb("#{model.ANNOT["color"]}"))[{inner}]'
                inner = f'#text(size: 0.1pt, fill: white)[{model.annotation_tag(n)}]' + inner
            out.append(inner)
        elif model.critic_edit(part) is not None:
            old, new = model.critic_edit(part)
            if model.ANNOT["enabled"]:       # revisione: vecchio barrato in rosso, nuovo sottolineato in verde
                if old:
                    out.append(f'#strike(stroke: rgb("#C62828"))[#text(fill: rgb("#C62828"))[{md_inline_to_typst(old)}]]')
                if new:
                    out.append(f'#underline(stroke: rgb("#2E7D32"))[#text(fill: rgb("#2E7D32"))[{md_inline_to_typst(new)}]]')
            else:
                keep = model.accepted_edit(old, new)
                out.append(md_inline_to_typst(keep) if keep else "")
        elif model.mark_text(part) is not None:
            out.append(f'#highlight(fill: rgb("#{HIGHLIGHT}"))[' + md_inline_to_typst(model.mark_text(part)) + "]")
        elif part.startswith("~~") and part.endswith("~~") and len(part) > 4:
            out.append("#strike[" + md_inline_to_typst(part[2:-2]) + "]")
        elif part.startswith("^") and part.endswith("^") and len(part) > 2:
            out.append("#super[" + esc(part[1:-1]) + "]")
        elif part.startswith("**") and part.endswith("**") and len(part) > 4:
            inner = part[2:-2]
            out.append("*" + (md_inline_to_typst(inner) if model.INLINE_MD.search(inner) else esc(inner)) + "*")
        elif (part.startswith("*") and part.endswith("*") and len(part) > 2) or \
             (part.startswith("_") and part.endswith("_") and len(part) > 2):
            out.append("_" + esc(part[1:-1]) + "_")
        else:
            out.append(esc(part))
    res = "".join(out)
    # a inizio riga Typst legge =, -, +, / e "1." come titolo/elenco
    return re.sub(r"^([=+/-]|\d+(?=\.))", lambda m: "\\" + m.group(0), res)


def paragraphs_of(text):
    """-> lista di paragrafi, ciascuno lista di righe (a-capo singoli = line break)."""
    paras = []
    for block in re.split(r"\n\s*\n", (text or "").strip()):
        lines = [ln.rstrip() for ln in block.split("\n") if ln.strip()]
        if lines:
            paras.append(lines)
    return paras


def render_paragraphs(paras):
    """Paragrafi -> markup Typst (una riga vuota separa i paragrafi, \\ per l'a-capo)."""
    out = []
    for lines in paras:
        out.append(" \\\n".join(md_inline_to_typst(ln) for ln in lines))
    return "\n\n".join(out)


# --------------------------------------------------------------------------
# Testo a due colonne
# --------------------------------------------------------------------------
# Typst NON bilancia #columns: riempie la prima colonna fino al fondo della regione, poi la seconda
# (un testo breve finisce tutto nella colonna di sinistra, uno a cavallo di pagina lascia 1-2 righe in
# fondo e il resto a sinistra). Qui le colonne si bilanciano misurando il testo: un testo breve diventa
# un blocco di altezza ~meta', non spezzabile (se non entra nello spazio rimasto va alla pagina dopo,
# bilanciato); un testo piu' lungo di `balance_max` della pagina scorre come #columns normale.
# link a un altro capitolo: ancora "ch_<id>" sul titolo; senza ancora il testo resta com'e'
CHLINK_DEF = ('#let chlink(anchor, body) = context {\n'
              '  if query(label(anchor)).len() > 0 { link(label(anchor), body) } else { body }\n}\n')

BALANCED_COLS = (
    # context (non layout): il risultato di layout() non si spezza fra le pagine; text-w e page-bottom
    # sono definiti nel preambolo. La posizione e' quella di un'ancora (#metadata) messa PRIMA del
    # blocco: con here() la decisione dipenderebbe dalla propria posizione (punto fisso: il blocco
    # spostato a pagina nuova ci resterebbe).
    '#let balanced-cols(anchor, gutter, max-frac, min-frac, body) = context {\n'
    '  let colw = (text-w - gutter) / 2\n'
    '  let h = measure(width: colw, body).height\n'
    '  let hb = h / 2 + 1.5 * text.size\n'
    '  let found = query(label(anchor))\n'
    '  let rem = if found.len() == 0 { none } else { page.height - page-bottom - found.first().location().position().y }\n'
    # primo passaggio (ancora senza posizione): flusso normale, spezzabile, mai un blocco che salta pagina
    '  if rem == none or hb > max-frac * page.height or (hb > rem and rem >= min-frac * page.height) {\n'
    '    columns(2, gutter: gutter, body)\n'
    '  } else { block(breakable: false, height: hb, columns(2, gutter: gutter, body)) }\n'
    '}\n')


_balanced_n = [0]


def balanced_markup(gutter_cm, balance_max, min_flow, body):
    _balanced_n[0] += 1
    name = f"bc-{_balanced_n[0]}"
    return (f'#metadata(none) <{name}>\n'
            f'#balanced-cols("{name}", {gutter_cm}cm, {balance_max}, {min_flow}, [{body}])')


def render_two_col_text(text, gutter_cm, indent_pt=0, balance_max=0.5, min_flow=0.2):
    """Testo su due colonne, bilanciate (vedi BALANCED_COLS); balance_max = 0 le disattiva."""
    paras = paragraphs_of(text)
    if not paras:
        return ""
    markup = render_paragraphs(paras)
    indent = (f'#set par(first-line-indent: (amount: {indent_pt}pt, all: true))\n'
              if indent_pt else "")
    if not balance_max:
        return f'#columns(2, gutter: {gutter_cm}cm)[{indent}{markup}]'
    return balanced_markup(gutter_cm, balance_max, min_flow, f"{indent}{markup}")


# --------------------------------------------------------------------------
# Immagini e tabella
# --------------------------------------------------------------------------
def text_style_markup(sc, gap=None):
    """set text/par per un blocco con stile proprio. gap = spazio fra paragrafi
    interni (default: space_before + space_after dello stile, come in Word)."""
    weight = "bold" if sc["bold"] else "regular"
    style = "italic" if sc["italic"] else "normal"
    if gap is None:
        gap = sc["space_before"] + sc["space_after"]
    return (f'#set text(font: "{sc["font"]}", size: {sc["size"]}pt, weight: "{weight}", '
            f'style: "{style}", fill: {typst_color(sc["color"])}, '
            f'top-edge: 0.75em, bottom-edge: -0.25em)\n'
            f'#set par(justify: {"true" if sc["align"] == "justify" else "false"}, '
            f'leading: {leading_pt(sc)}pt, spacing: {round(leading_pt(sc) + gap, 2)}pt, '
            f'first-line-indent: 0pt)\n')


def render_quote(cfg, q):
    """space_before/space_after dello stile = spazio ESTERNO al blocco; fra i paragrafi
    interni paragraph_gap; la fonte e' una riga a capo (allineata a destra) nello stesso
    paragrafo dell'ultimo capoverso, quindi senza spazio sopra.
    Ultima riga e fonte non si separano mai: citazioni brevi (< keep_together_chars) sono un
    blocco unico non spezzabile; per le lunghe, penalita' altissime su vedove/orfane."""
    sc = style_cfg(cfg, "quote", fallback="normal")
    qcfg = cfg.get("styles", {}).get("quote", {})
    gap = qcfg.get("paragraph_gap", 4)
    body = render_paragraphs(paragraphs_of(q.text))
    src = f' \\\n#h(1fr) — {md_inline_to_typst(q.source)}' if q.source else ""
    inner = f'{text_style_markup(sc, gap)}#set text(costs: (widow: 1000%, orphan: 1000%))\n{body}{src}'
    short = len(q.text) + len(q.source or "") < qcfg.get("keep_together_chars", 700)
    block = f'#block(breakable: false)[{inner}]' if short else f'#[{inner}]'
    return (f'#v({sc["space_before"]}pt, weak: true)\n'
            f'#pad(left: {sc["indent_left"]}pt, right: {sc["indent_right"]}pt)[\n{block}]\n'
            f'#v({sc["space_after"]}pt, weak: true)')


def render_styled(cfg, st):
    """Paragrafi con stile personalizzato (`::: {attributi}`): font, corpo, peso, allineamento, spazi."""
    sc = st.style
    body = "\n\n".join(md_inline_to_typst(p) for p in st.text.split("\n\n"))
    if sc.get("case") == "upper":
        body = f"#upper[{body}]"
    elif sc.get("case") == "lower":
        body = f"#lower[{body}]"
    elif sc.get("case") == "smallcaps":
        body = f"#smallcaps[{body}]"
    lead = leading_pt(sc)
    just = sc["align"] == "justify"
    ind = f'first-line-indent: {sc["first_line_indent"]}pt, ' if sc["first_line_indent"] else ""
    track = f'tracking: {sc["tracking"]}pt, ' if sc.get("tracking") else ""
    # width: blocco piu' stretto della pagina, collocato secondo `align` (a sinistra se giustificato)
    wspec = sc.get("width")
    if wspec:
        wcm = None if wspec.endswith("%") else model.length_cm(wspec, 0)
        blk_w = wspec if wspec.endswith("%") else (f"{wcm:.2f}cm" if wcm else "100%")
    else:
        blk_w = "100%"
    box_al = typst_align("left" if just else sc["align"])
    open_ = f'#align({box_al}, block(width: {blk_w})[' if wspec else f'#block(width: {blk_w})['
    close_ = ')' if wspec else ''
    return (f'#v({round(sc["space_before"], 2)}pt)\n'
            f'{open_}#set text(font: "{sc["font"]}", size: {sc["size"]}pt, '
            f'weight: "{"bold" if sc["bold"] else "regular"}", style: "{"italic" if sc["italic"] else "normal"}", '
            f'{track}fill: {typst_color(sc["color"])})\n'
            f'#set par(justify: {"true" if just else "false"}, leading: {lead}pt, spacing: {lead}pt, {ind}'
            f'linebreaks: "optimized")\n'
            f'#align({typst_align("left" if just else sc["align"])})[{body}]]{close_}\n'
            f'#v({round(sc["space_after"], 2)}pt)')


def render_list(cfg, lb):
    sc = style_cfg(cfg, "list", fallback="normal")
    hang = -sc["first_line_indent"] or 12
    left = sc["indent_left"] or 18
    marker = "+" if lb.ordered else "-"
    lines = [f'{"  " * d}{marker} {md_inline_to_typst(t)}' for d, t in lb.items]
    return (f'#v({sc["space_before"]}pt, weak: true)\n'
            f'#[{text_style_markup(sc, 0)}#set list(indent: {left - hang}pt, body-indent: {hang}pt)\n'
            f'#set enum(indent: {left - hang}pt, body-indent: {hang}pt)\n'
            + "\n".join(lines) + f']\n#v({sc["space_after"]}pt, weak: true)')


def render_bibliography(cfg, bib):
    """Voci con rientro sporgente (styles.bibliography: indent_left e first_line_indent negativo)."""
    sc = style_cfg(cfg, "bibliography", fallback="normal")
    hang = -sc["first_line_indent"] or 14
    entries = "\n\n".join(md_inline_to_typst(t) for _, t in bib.entries)
    return (f'#[{text_style_markup(sc, sc["space_after"])}#set par(hanging-indent: {hang}pt)\n'
            f'{entries}\n]')


def render_flow_text(text, indent_pt=0):
    """Testo a colonna singola (flusso normale della pagina)."""
    markup = render_paragraphs(paragraphs_of(text))
    if not indent_pt:
        return markup
    return f'#[#set par(first-line-indent: (amount: {indent_pt}pt, all: true))\n{markup}]'


def compute_width_cm(path, max_w_cm, max_h_cm):
    try:
        with Image.open(path) as im:
            w, h = im.size
    except Exception:
        return max_w_cm
    if not w or not h:
        return max_w_cm
    return min(max_w_cm, max_h_cm * w / h)


TYPST_IMAGE_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".pdf"}


def typst_readable(path):
    """Typst non legge TIFF/BMP: li converte (una volta, in cache) in PNG, con lo stesso
    profilo di colore convertito in RGB; gli altri formati passano invariati."""
    path = Path(path)
    if path.suffix.lower() in TYPST_IMAGE_EXT:
        return path
    import hashlib
    cache = Path(tempfile.gettempdir()) / "volumen-image-cache"
    cache.mkdir(exist_ok=True)
    key = hashlib.sha1(f"{path}:{path.stat().st_mtime_ns}".encode()).hexdigest()[:16]
    out = cache / f"{key}.png"
    if not out.exists():
        with Image.open(path) as im:
            im.convert("RGBA" if "A" in im.getbands() else "RGB").save(out)
    return out


def render_image(cfg, path, caption, max_w_cm, max_h_cm, space_before_pt=None, space_after_pt=None,
                 width_cm=None, height_cm=None, align="center"):
    """Immagine + didascalia come blocchi separati (niente #figure: la numerazione
    'Fig. <prefisso>.<n>.' e' gia' calcolata da questo script, non va duplicata
    dal contatore automatico 'Figure N:' di Typst). Immagine e didascalia sono
    dentro un unico block(breakable: false): se non entrano nello spazio rimasto
    in pagina, passano intere alla pagina dopo, invece di spezzarsi fra le due."""
    path = typst_readable(path)
    if width_cm or height_cm:        # dimensioni esplicite (attributi width/height): scavalcano i tetti
        w = compute_width_cm(path, width_cm or 1000, height_cm or 1000)
    else:
        w = compute_width_cm(path, max_w_cm, max_h_cm)
    cap_sc = style_cfg(cfg, "caption")
    cap_align = typst_align(cap_sc["align"])
    group = [f'#align({align})[#image("{esc_str(str(path))}", width: {w:.2f}cm)]']
    if caption:
        weight = "bold" if cap_sc["bold"] else "regular"
        content = esc(caption)
        if cap_sc["italic"]:
            content = f"_{content}_"
        group.append(f'#align({cap_align})[#text(font: "{cap_sc["font"]}", size: {cap_sc["size"]}pt, '
                     f'weight: "{weight}", fill: {typst_color(cap_sc["color"])})[{content}]]')
    if caption:       # ancora nascosta per l'elenco delle figure (vedi list_of_figures_markup)
        group.insert(0, f'#place(hide(figure([], kind: "volumen-fig", supplement: none, outlined: true, '
                        f'caption: [{esc(caption)}])))')
    parts = []
    if space_before_pt is not None:
        parts.append(f"#v({space_before_pt}pt)")
    # larghezza del blocco = quella dell'immagine (con un minimo): la didascalia va a capo sotto l'immagine,
    # senza allargare la colonna della figura (wrap) ne' estendersi oltre l'immagine
    cap_w = max(w, cfg.get("images", {}).get("min_caption_cm", 5.0))
    parts.append(f"#align({align}, block(breakable: false, width: {cap_w:.2f}cm)[\n" + "\n".join(group) + "\n])")
    if space_after_pt is not None:
        parts.append(f"#v({space_after_pt}pt)")
    return "\n".join(parts)


def render_table(cfg, header, rows, ratios=None, aligns=None, empty_cell=None, caption="", markup=True):
    """Larghezze colonna da ratios (pesi relativi, non cm), spessore riga da table.rule_pt/
    header_rule_pt, font/corpo/grassetto/colore di intestazione e corpo da styles.table_header/
    table_body. markup=True: le celle possono contenere **grassetto**/*corsivo*."""
    tcfg = cfg.get("table", {})
    header_sc = style_cfg(cfg, "table_header")
    body_sc = style_cfg(cfg, "table_body")
    n = len(header)
    ratios = ratios or [1] * n
    aligns = aligns or [body_sc["align"]] * n
    rule_pt = tcfg.get("rule_pt", 0.75)
    header_rule_pt = tcfg.get("header_rule_pt", 0.5)

    def cell_text(value, sc):
        weight = "bold" if sc["bold"] else "regular"
        content = md_inline_to_typst(str(value)) if markup else esc(str(value))
        if sc["italic"]:
            content = f"_{content}_"
        return (f'#text(font: "{sc["font"]}", size: {sc["size"]}pt, weight: "{weight}", '
                f'fill: {typst_color(sc["color"])})[{content}]')

    def cell(value, sc, i):
        return f'table.cell(align: {typst_align(aligns[i])})[{cell_text(value, sc)}]'

    header_cells = [cell(c, header_sc, i) for i, c in enumerate(header)]
    body_cell_rows = []
    for row in rows:
        vals = [v if (v not in (None, "") or empty_cell is None) else empty_cell for v in row]
        body_cell_rows.append(", ".join(cell("" if v is None else v, body_sc, i)
                                        for i, v in enumerate(vals)))
    columns = ", ".join(f"{r}fr" for r in ratios)

    lines = [
        "#table(",
        f"  columns: ({columns}),",
        "  stroke: none,",
        f"  table.hline(stroke: {rule_pt}pt),",
        # table.header() ripete la riga (e la regola sotto) su ogni pagina in
        # cui la tabella si spezza - come set_repeat_header() del renderer DOCX.
        "  table.header(",
        "    " + ", ".join(header_cells) + ",",
        "  ),",
        f"  table.hline(stroke: {header_rule_pt}pt),",
    ]
    lines += ["  " + row_str + "," for row_str in body_cell_rows]
    lines.append(f"  table.hline(stroke: {rule_pt}pt),")
    lines.append(")")
    # nelle celle niente giustificazione ne' sillabazione (colonne strette: spazi e trattini strani)
    table = "#[#set par(justify: false)\n#set text(hyphenate: false)\n" + "\n".join(lines) + "\n]"
    if caption:
        cap_sc = style_cfg(cfg, "caption")
        content = md_inline_to_typst(caption)
        if cap_sc["italic"]:
            content = f"_{content}_"
        table = (f'#block(sticky: true, width: 100%)[#align({typst_align(cap_sc["align"])})[#text('
                 f'font: "{cap_sc["font"]}", size: {cap_sc["size"]}pt, fill: {typst_color(cap_sc["color"])})'
                 f'[{content}]]#v({cap_sc["space_after"]}pt)]\n' + table)
    return table


# --------------------------------------------------------------------------
# Preambolo (pagina, font, controfigura numerazione)
# --------------------------------------------------------------------------
def footnote_markup(cfg):
    """Stile delle note (styles.footnote, ripiego su normal, ma piu' piccolo): corpo, interlinea,
    separatore breve sopra le note."""
    sc = style_cfg(cfg, "footnote", fallback="normal")
    weight = "bold" if sc["bold"] else "regular"
    return (f'#show footnote.entry: it => {{\n'
            f'  set text(font: "{sc["font"]}", size: {sc["size"]}pt, weight: "{weight}", '
            f'fill: {typst_color(sc["color"])})\n'
            f'  set par(justify: {"true" if sc["align"] == "justify" else "false"}, '
            f'leading: {leading_pt(sc)}pt, first-line-indent: 0pt, spacing: {leading_pt(sc)}pt)\n'
            f'  it\n}}\n'
            f'#set footnote.entry(separator: line(length: 30%, stroke: 0.5pt), '
            f'clearance: 6pt, gap: {sc["space_after"] or 2}pt)')


def page_margins_io(pg):
    """(interno, esterno) in cm: margin_interior/margin_exterior, altrimenti margin_left/right_cm."""
    return (pg.get("margin_interior", pg.get("margin_left_cm", 2.5)),
            pg.get("margin_exterior", pg.get("margin_right_cm", 2.5)))


def preamble(cfg, with_header=True, header_only=False):
    pg = cfg.get("page", {})
    if pg.get("size", "A4").upper() == "A4":
        page_w, page_h = 21.0, 29.7
    else:  # Letter
        page_w, page_h = 21.59, 27.94
    margin_top = pg.get("margin_top_cm", 2.5)
    margin_bottom = pg.get("margin_bottom_cm", 2.5)
    margin_interior, margin_exterior = page_margins_io(pg)
    normal = style_cfg(cfg, "normal")
    normal_justify = normal["align"] == "justify"
    # In Typst, par.spacing e' l'INTERO spazio fra i riquadri di riga di due
    # paragrafi (sostituisce il leading, non lo integra). Per avere lo stesso
    # passo di Word (line_height + space_before + space_after) ci si parte
    # quindi dal leading, non dall'altezza di riga intera.
    spacing_pt = round(leading_pt(normal) + normal["space_before"] + normal["space_after"], 2)

    hcfg = cfg.get("header", {})
    header_markup = ""
    if hcfg.get("enabled", True):
        title_sc = style_cfg(cfg, "header_title")
        pn_sc = style_cfg(cfg, "header_pagenum")
        rule = hcfg.get("rule", {})
        start_page = hcfg.get("start_page", 1)
        show_pn = cfg.get("page", {}).get("page_numbers", True)
        rule_pt = rule.get("size_eighths_pt", 4) / 8
        title_weight = "bold" if title_sc["bold"] else "regular"
        pn_weight = "bold" if pn_sc["bold"] else "regular"
        default_title = esc_str(hcfg.get("title", ""))
        # Specchiata fra pagine dispari e pari, come in build.py: il titolo
        # (da config) verso l'interno (rilegatura), il numero di pagina verso
        # l'esterno. Dispari: titolo a sinistra, numero a destra. Pari:
        # numero a sinistra, titolo a destra. Una riga sotto, come in build.py.
        header_markup = (
            f'#counter(page).update({start_page})\n'
            f'#set page(header: context {{\n'
            f'  let pg = counter(page).get().first()\n'
            f'  let odd = calc.rem(pg, 2) == 1\n'
            # titolo = capitolo che inizia in questa pagina, altrimenti l'ultimo iniziato prima
            # (segnaposto <chapter-start> emessi dal renderer); default = header.title
            f'  let starts = query(<chapter-start>)\n'
            f'  let here-page = here().page()\n'
            f'  let on-page = starts.filter(m => m.location().page() == here-page)\n'
            f'  let before = starts.filter(m => m.location().page() < here-page)\n'
            f'  let cur-start = if on-page.len() > 0 {{ on-page.first().value }} '
            f'else if before.len() > 0 {{ before.last().value }} else {{ (title: "{default_title}", left: none) }}\n'
            f'  let cur = cur-start.title\n'
            # pagine pari (sinistre): autore (header.left_pages), se manca/"title" come le destre
            f'  let cur-left = if cur-start.left != none {{ cur-start.left }} else {{ cur }}\n'
            f'  let title-style = it => text(font: "{title_sc["font"]}", size: {title_sc["size"]}pt, '
            f'weight: "{title_weight}", style: "{"italic" if title_sc["italic"] else "normal"}", it)\n'
            f'  let title-part = title-style[#cur]\n'
            f'  let left-part = title-style[#cur-left]\n'
            f'  let num-part = text(font: "{pn_sc["font"]}", size: {pn_sc["size"]}pt, '
            f'weight: "{pn_weight}")[{"#pg" if show_pn else ""}]\n'
            f'  let row = if odd [#title-part #h(1fr) #num-part] '
            f'else [#num-part #h(1fr) #left-part]\n'
            f'  let ends = query(<chapter-end>).map(m => m.location().page())\n'
            f'  let start-pages = starts.map(m => m.location().page())\n'
            # pagina vuota inserita per far iniziare il capitolo a destra: dopo una fine capitolo e prima del prossimo inizio
            f'  let blank = ends.any(e => e < here-page and start-pages.filter(sp => sp > e).fold(1000000, calc.min) > here-page)\n'
            f'  let hide = ({"true" if hcfg.get("skip_chapter_first_page", True) else "false"} and on-page.len() > 0) or blank\n'
            f'  block(width: 100%)[#if not hide [\n'
            f'    #row\n'
        )
        if rule.get("enabled", True):
            header_markup += (
                f'    #v({rule.get("space_pt", 2)}pt)\n'
                f'    #line(length: 100%, stroke: {rule_pt}pt + rgb("#{rule.get("color", "000000")}"))\n'
            )
        header_markup += "  ]]\n})\n"
    if header_only:
        return header_markup

    return (
        f'#let text-w = {page_w - margin_interior - margin_exterior}cm\n#let page-bottom = {margin_bottom}cm\n' +
        CHLINK_DEF +
        BALANCED_COLS +
        f'#set page(width: {page_w}cm, height: {page_h}cm, margin: (inside: {margin_interior}cm, '
        f'outside: {margin_exterior}cm, top: {margin_top}cm, bottom: {margin_bottom}cm))\n'
        f'#set text(font: "{normal["font"]}", size: {normal["size"]}pt, '
        f'top-edge: 0.75em, bottom-edge: -0.25em, fill: {typst_color(normal["color"])}, '
        f'hyphenate: {"true" if cfg.get("typography", {}).get("hyphenate", False) else "false"})\n'
        f'#set align({typst_align(normal["align"])})\n'
        f'#set par(justify: {"true" if normal_justify else "false"}, leading: {leading_pt(normal)}pt, '
        f'spacing: {spacing_pt}pt)\n'
        f'{header_markup if with_header else "#set page(header: none)"}\n'
        f'{footnote_markup(cfg)}\n'
        r'''
'''
    )


def chapter_break(cfg):
    """Salto pagina prima di un capitolo. Con page.chapter_start = "right" (default) il capitolo inizia
    sempre in una pagina destra (dispari): se cadrebbe a sinistra Typst inserisce una pagina vuota
    (pagebreak to: "odd"); l'intestazione la riconosce e non la stampa (vedi header_markup: e' una pagina
    compresa fra <chapter-end> e il <chapter-start> successivo). La numerazione la conta come ogni altra pagina."""
    if cfg.get("page", {}).get("chapter_start", "right") != "right":
        return "#pagebreak(weak: true)"
    return '#metadata(none) <chapter-end>\n#pagebreak(weak: true, to: "odd")'


def toc_entry_rule(cfg, gap_cm, authors=True):
    """Voci dell'indice: il testo va a capo almeno gap_cm prima del numero di pagina (il testo sta in una
    colonna, il numero in un'altra preceduta da gap_cm vuoti), con i puntini di guida continui fino al numero.
    Se authors: sotto la voce di un capitolo con autori, una riga con i loro nomi (stile `toc_author`)."""
    sc = style_cfg(cfg, "toc_author", fallback="chapter_author")
    rule = ('#show outline.entry: it => {\n'
            '  let entry = link(it.element.location(), pad(left: (it.level - 1) * 1em, grid(\n'
            '    columns: (1fr, auto), align: (left, right + bottom),\n'
            # i puntini sono un unico riempimento: la box da 1fr e' allargata di gap_cm (sconfina nello
            # spazio vuoto davanti al numero di pagina) e si ferma poco prima del numero
            f'    [#it.body()#box(width: 1fr, layout(size => box(width: size.width + {gap_cm}cm - 0.5em, it.fill)))],\n'
            f'    [#h({gap_cm}cm)#it.page()])))\n')
    if not authors:
        return rule + '  entry\n}'
    return (rule + '  entry\n  let s = it.element.supplement\n'
            '  if s != none and s != auto {\n'
            f'    pad(left: (it.level - 1) * 1em, text(font: "{sc["font"]}", size: {sc["size"]}pt, '
            f'style: "{"italic" if sc["italic"] else "normal"}", fill: {typst_color(sc["color"])}, s))\n'
            f'    v({sc["space_after"]}pt)\n  }}\n}}')


def list_of_figures_markup(cfg, lof):
    """Elenco di tutte le figure con didascalia (anche piante e figure di fine scheda), nell'ordine del
    volume. E' un apparato di consultazione: corpo ridotto, due colonne, voci compatte con il numero di
    pagina in coda alla didascalia (dopo `separator`), senza puntini di guida."""
    size = lof.get("size", 8)
    sep = esc(str(lof.get("separator", ": ")))
    ncol = int(lof.get("columns", 2))
    nsc = style_cfg(cfg, "normal")
    return "\n".join([
        '#metadata((title: "", left: "")) <chapter-start>',
        heading_markup(cfg, heading_style(cfg, 2), lof.get("title", "List of Figures")),
        '#[',
        '#show outline.entry: it => link(it.element.location(), block(width: 100%, spacing: 0.45em)['
        f'#it.body()#[{sep}]#it.page()])',
        f'#set text(font: "{nsc["font"]}", size: {size}pt)',
        f'#set par(justify: false, leading: {round(size * 0.3, 2)}pt, hanging-indent: 1.2em)',
        f'#columns({ncol}, gutter: {lof.get("gutter_cm", 0.8)}cm)[',
        '#outline(title: none, target: figure.where(kind: "volumen-fig"), indent: 0em)',
        ']',
        ']'])


def heading_markup(cfg, style_name, text, level=None, authors=None, anchor=None):
    """Spazio sopra/sotto esplicito (v()), non affidato allo spazio 'ambientale'
    fra blocchi di Typst: quello varia a seconda di cosa precede (una colonna
    bilanciata corta o uno scorrimento naturale lungo danno spaziature diverse
    anche con lo stesso stile), mentre qui due titoli con lo stesso stile
    devono avere sempre la stessa spaziatura."""
    sc = style_cfg(cfg, style_name)
    weight = "bold" if sc["bold"] else "regular"
    hyph = "true" if cfg.get("typography", {}).get("hyphenate", False) else "false"
    content = esc(text)
    if sc["italic"]:
        content = f"_{content}_"
    heading = (f'#align({typst_align(sc["align"])})[#par(leading: {leading_pt(sc)}pt, justify: {"true" if sc["align"] == "justify" else "false"})'
              f'[#text(font: "{sc["font"]}", size: {sc["size"]}pt, weight: "{weight}", hyphenate: {hyph}, '
              f'fill: {typst_color(sc["color"])})[{content}]]]')
    # titolo "vero" (nascosto, fuori flusso) per l'indice #outline e i segnalibri del PDF: quello
    # visibile e' impaginato a mano (stili, spaziatura). level=None: non compare nell'indice.
    # authors: finiscono nel "supplement" del titolo, da cui l'indice li legge (vedi toc_authors_rule)
    supp = f"[{esc(', '.join(authors))}]" if authors else "none"
    lab = f"<{anchor}>" if anchor else ""     # destinazione dei link tra capitoli
    real = (f'#place(hide[#heading(level: {level}, outlined: true, bookmarked: true, numbering: none, '
            f'supplement: {supp})[{esc(text)}]{lab}])\n' if level else "")
    return (real + f'#v({sc["space_before"]}pt, weak: true)\n'
            # sticky: il titolo non resta mai solo in fondo a una colonna/pagina
            f'#block(sticky: true, width: 100%)[{heading}\n#v({sc["space_after"]}pt)]')


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------


# --------------------------------------------------------------------------
# Volume -> sorgente .typ -> PDF
# --------------------------------------------------------------------------
class Wrap:
    """Figura con testo che le scorre intorno (position left/right): la figura + i primi
    paragrafi del testo che segue (pacchetto Typst wrap-it)."""
    def __init__(self, fig, paras):
        self.fig, self.paras = fig, paras


def wrap_pass(blocks, flow):
    """Fonde ogni Figure con position left/right con il Text che la segue (a 1 colonna e nel
    flusso a colonne); il resto del Text (oltre `wrap` paragrafi) resta un Text normale."""
    out, i = [], 0
    while i < len(blocks):
        b = blocks[i]
        if (isinstance(b, model.Figure) and b.position in ("left", "right")
                and i + 1 < len(blocks) and isinstance(blocks[i + 1], model.Text)):
            paras = paragraphs_of(blocks[i + 1].text)
            n = max(1, b.wrap)
            out.append(Wrap(b, paras[:n]))
            if len(paras) > n:
                out.append(model.Text("\n\n".join("\n".join(p) for p in paras[n:]), blocks[i + 1].columns))
            i += 2
            continue
        out.append(b)
        i += 1
    return out


class TextFlow:
    """Testi a due colonne separati solo da sottotitoli (es. descrizione + Material Culture): un
    unico blocco di colonne bilanciate, cosi' il flusso sinistra/destra non si spezza al titolo."""
    def __init__(self, items):
        self.items = items


def group_text_flow(blocks, min_level):
    """Raggruppa Text(columns>1) [Heading(level >= min_level) Text(columns>1)]* in un TextFlow.
    Un titolo che non e' seguito da un testo a colonne (es. quello della tabella) resta fuori."""
    def col_text(b):
        return isinstance(b, model.Text) and b.columns > 1 and b.text.strip()
    out, i = [], 0
    while i < len(blocks):
        b = blocks[i]
        if not col_text(b):
            out.append(b)
            i += 1
            continue
        items, i = [b], i + 1
        while (i + 1 < len(blocks) and isinstance(blocks[i], model.Heading)
               and blocks[i].level >= min_level and not blocks[i].page_break_before
               and col_text(blocks[i + 1])):
            items += [blocks[i], blocks[i + 1]]
            i += 2
        out.append(items[0] if len(items) == 1 else TextFlow(items))
    return out


def build_source(cfg, volume):
    model.ANNOT["items"] = []
    global HIGHLIGHT
    HIGHLIGHT = cfg.get("typography", {}).get("highlight_color", HIGHLIGHT)
    global LINKS
    LINKS = cfg.get("links", {})
    tcfg = cfg.get("typst", {})
    gutter_cm = tcfg.get("column_gutter_cm", 1.0)
    icfg = cfg.get("images", {})
    max_w_cm = icfg.get("max_width_cm", 15.0)
    max_h_cm = icfg.get("max_height_cm", 20.0)
    fig_before = icfg.get("figure_space_before_pt", 4)
    fig_after = icfg.get("figure_space_after_pt")
    pg = cfg.get("page", {})
    page_w_cm = 21.0 if pg.get("size", "A4").upper() == "A4" else 21.59
    usable_cm = page_w_cm - sum(page_margins_io(pg))
    fig_classes = icfg.get("classes", {})
    table_classes = cfg.get("table", {}).get("classes", {})
    table_after = cfg.get("table", {}).get("space_after_pt", 14)
    empty_cell = cfg.get("table", {}).get("empty_cell", "–")
    indent_pt = style_cfg(cfg, "normal")["first_line_indent"]

    float_pos = icfg.get("float_position", "auto")    # auto | top | bottom

    uses_wrap = []

    def float_fig(f, in_flow, col_w_cm):
        """Nel flusso a colonne la figura fluttua a piena larghezza (in cima/in fondo alla pagina,
        scope 'parent'): il testo continua a riempire le colonne, senza buchi. Fuori dal flusso
        e' un blocco normale con lo spazio sopra/sotto. Attributi per figura (Markdown):
        width/height (dimensioni esplicite), position = auto|top|bottom (a piena larghezza),
        column (dentro la colonna); left/right sono gestite da Wrap."""
        pos = f.position or "auto"
        in_col = pos in ("column", "left", "right")
        ref = col_w_cm if (in_flow and in_col) else usable_cm
        w_cm, h_cm = model.length_cm(f.width, ref), model.length_cm(f.height, ref)
        if not in_flow:
            return render_image(cfg, f.path, f.caption, max_w_cm, max_h_cm,
                                space_before_pt=fig_before, space_after_pt=fig_after,
                                width_cm=w_cm, height_cm=h_cm)
        # flow_max_height_cm: tetto all'altezza delle figure fluttuanti, cosi' che due figure sulla
        # stessa pagina (una in cima, una in fondo) lascino comunque spazio al testo
        flow_h = icfg.get("flow_max_height_cm", max_h_cm)
        gap = max((fig_before or 0), (fig_after or 0), 10)
        if in_col:
            body = render_image(cfg, f.path, f.caption, min(max_w_cm, col_w_cm), flow_h,
                                width_cm=min(w_cm, col_w_cm) if w_cm else None, height_cm=h_cm)
            return f'#place(auto, float: true, clearance: {gap}pt)[{body}]'
        body = render_image(cfg, f.path, f.caption, max_w_cm, flow_h, width_cm=w_cm, height_cm=h_cm)
        align = "auto" if pos == "auto" and float_pos == "auto" else \
            f"{pos if pos in ('top', 'bottom') else float_pos} + center"
        return f'#place({align}, scope: "parent", float: true, clearance: {gap}pt)[{body}]'

    def wrap_fig(w, col_w_cm, indent):
        f = w.fig
        uses_wrap.append(1)
        width = model.length_cm(f.width, col_w_cm) or icfg.get("wrap_width_cm", 5.0)
        body = render_image(cfg, f.path, f.caption, col_w_cm, 1000, width_cm=min(width, col_w_cm),
                            height_cm=model.length_cm(f.height, col_w_cm))
        # rientranza esplicita (#h) a ogni paragrafo, senza #set par: wrap-it spezza il testo e il #set
        # finiva sul pezzo sbagliato (primo paragrafo senza rientranza, continuazione con rientranza)
        pre = f"#h({indent}pt)" if indent else ""
        text = "\n\n".join(pre + t for t in render_paragraphs(w.paras).split("\n\n"))
        # colonne esplicite: con due colonne auto, se figura larga + testo superano lo spazio la griglia
        # restringe la colonna della figura e l'immagine (a larghezza fissa) sborda sul testo
        cols = "(1fr, auto)" if f.position == "right" else "(auto, 1fr)"
        return (f'#wrap-content(align: {f.position}, columns: {cols}, column-gutter: {icfg.get("wrap_gutter_pt", 12)}pt, '
                f'[{body}], [{text}])')

    parts = [preamble(cfg, with_header=not volume.front)]
    if volume.front:
        # frontespizio e colophon: senza intestazione ne' numero; l'indice (o il primo capitolo) parte su pagina
        # destra e li' la numerazione riparte da start_page, come senza frontmatter
        for fi, fch in enumerate(volume.front):
            if fi > 0:
                parts.append("#pagebreak()")
            for b in fch.blocks:
                if isinstance(b, model.StyledText):
                    parts.append(render_styled(cfg, b))
                elif isinstance(b, model.PageBreak):
                    parts.append("#pagebreak()")
                elif isinstance(b, model.Text):
                    parts.append(render_flow_text(b.text, 0))
                elif isinstance(b, model.Heading):
                    parts.append(heading_markup(cfg, heading_style(cfg, b.level), b.text))
                elif isinstance(b, model.Figure):
                    parts.append(render_image(cfg, b.path, "", max_w_cm, max_h_cm,
                                              width_cm=model.length_cm(b.width, usable_cm),
                                              height_cm=model.length_cm(b.height, usable_cm),
                                              align=b.align or "center"))
        parts.append('#pagebreak(weak: true, to: "odd")')
        parts.append(preamble(cfg, header_only=True))
    toc = volume.meta.get("toc") or {}
    if toc.get("enabled"):
        # titolo dell'indice impaginato a mano (stile h2, fuori dall'indice); voci con font del testo
        parts.append('#metadata((title: "", left: "")) <chapter-start>')      # pagina senza intestazione corrente
        parts.append(heading_markup(cfg, heading_style(cfg, 2), toc.get("title", "Contents")))
        parts.append(toc_entry_rule(cfg, toc.get("page_gap_cm", 1.5), authors=toc.get("authors", True)))
        parts.append(f'#outline(title: none, depth: {toc.get("depth", 2)}, indent: 1em)\n{chapter_break(cfg)}')
    for i, ch in enumerate(volume.chapters):
        starts_with_part = bool(ch.blocks) and isinstance(ch.blocks[0], model.PartTitle)
        if i > 0 and ch.new_page:
            parts.append(chapter_break(cfg))
        # segnaposto letto dall'intestazione corrente: titolo del capitolo che inizia in questa pagina
        running = "" if starts_with_part else (ch.running_title or ch.title)
        left = None if starts_with_part else model.running_left(ch, volume, cfg.get("header", {}))
        left_typ = "none" if left is None else f'"{esc_str(left)}"'
        parts.append(f'#metadata((title: "{esc_str(running)}", left: {left_typ})) <chapter-start>')
        # column_flow > 1: dopo il titolo, testo/titoli/citazioni/elenchi scorrono in un unico
        # flusso a colonne; figure e tabelle lo interrompono e occupano tutta la larghezza.
        flow = ch.column_flow if ch.column_flow > 1 else 0
        chunk = []

        def flush_flow():
            if chunk:
                # place.flush: le figure ancora "in volo" vanno prima della fine del blocco
                parts.append(f'#columns({flow}, gutter: {gutter_cm}cm)[\n' + "\n\n".join(chunk)
                             + '\n#place.flush()\n]')
                chunk.clear()

        col_w_cm = (usable_cm - gutter_cm * (flow - 1)) / flow if flow else usable_cm
        pass_blocks = wrap_pass(ch.blocks, flow)
        if not flow:
            pass_blocks = group_text_flow(pass_blocks, tcfg.get("flow_heading_min_level", 3))
        for k, b in enumerate(pass_blocks):
            full_width = isinstance(b, model.PartTitle) or (
                isinstance(b, model.Table) and (len(b.rows) > 20 or table_classes.get(b.klass, {}).get("full_width", False)))   # le figure fluttuano (vedi float_fig)
            in_flow = bool(flow) and k > 0 and not full_width    # k=0: titolo del capitolo
            if flow and full_width:
                flush_flow()
            out = chunk if in_flow else parts
            if isinstance(b, model.Heading):
                pb = "#pagebreak()\n" if b.page_break_before else ""
                opener = k == 0 and b.level == 1     # titolo h1 di capitolo: parte a offset_pct della pagina
                if opener:
                    out.append(f'#v({cfg.get("chapter_opener", {}).get("offset_pct", 33)}%)')
                out.append(f"{pb}{heading_markup(cfg, heading_style(cfg, b.level), b.text, level=b.level, authors=ch.authors if k == 0 else None, anchor=model.chapter_anchor(ch.id) if k == 0 else (model.chapter_anchor(b.anchor) if b.anchor else None))}")
                if k == 0 and ch.authors:
                    asc = style_cfg(cfg, "chapter_author", fallback="normal")
                    out.append(f'#v({asc["space_before"]}pt)\n#align({typst_align(asc["align"])})[#text('
                               f'font: "{asc["font"]}", size: {asc["size"]}pt, '
                               f'fill: {typst_color(asc["color"])})[{esc(", ".join(ch.authors))}]]\n#v(12pt)')
            elif isinstance(b, model.Bibliography):
                out.append("#place.flush()")     # prima le figure ancora in attesa, poi la bibliografia
                out.append(heading_markup(cfg, heading_style(cfg, b.level), b.title))
                out.append(render_bibliography(cfg, b))
            elif isinstance(b, model.StyledText):
                out.append(render_styled(cfg, b))
            elif isinstance(b, model.PageBreak):
                out.append("#pagebreak()")
            elif isinstance(b, model.Quote):
                out.append(render_quote(cfg, b))
            elif isinstance(b, model.ListBlock):
                out.append(render_list(cfg, b))
            elif isinstance(b, model.PartTitle):
                sc = style_cfg(cfg, heading_style(cfg, b.level))
                out.append(f'#place(hide(heading(level: {b.level}, outlined: true, bookmarked: true, '
                           f'numbering: none, supplement: none)[{esc(b.text)}]))\n'
                           f'#align(horizon + center)[#text(font: "{sc["font"]}", '
                             f'size: {sc["size"]}pt, weight: "bold", fill: {typst_color(sc["color"])})'
                             f'[{esc(b.text)}]]\n#pagebreak()')
            elif isinstance(b, TextFlow):
                body = "\n\n".join(
                    heading_markup(cfg, heading_style(cfg, it.level), it.text, level=it.level)
                    if isinstance(it, model.Heading) else render_paragraphs(paragraphs_of(it.text))
                    for it in b.items)
                indent = (f'#set par(first-line-indent: (amount: {indent_pt}pt, all: true))\n'
                          if indent_pt else "")
                out.append(balanced_markup(gutter_cm, tcfg.get("balance_columns_max", 0.5),
                                           tcfg.get("balance_min_flow", 0.2), f"{indent}{body}"))
            elif isinstance(b, model.Text):
                if not b.text.strip():
                    continue
                if b.columns > 1:
                    out.append(render_two_col_text(b.text, gutter_cm, indent_pt,
                                                       cfg.get("typst", {}).get("balance_columns_max", 0.5),
                                                       cfg.get("typst", {}).get("balance_min_flow", 0.2)))
                else:
                    out.append(render_flow_text(b.text, indent_pt))
            elif isinstance(b, model.Figure) and b.klass in fig_classes:
                # Classe di figura (images.classes.<nome>): larghezza scollegata da images.max_width_cm/
                # max_height_cm (width_pct della larghezza utile), altezza libera secondo le proporzioni.
                fc = fig_classes[b.klass]
                out.append(render_image(cfg, b.path, b.caption, usable_cm * fc.get("width_pct", 100) / 100, 1000,
                                          space_before_pt=fc.get("space_before_pt", fig_before),
                                          space_after_pt=fc.get("space_after_pt", fig_before)))
            elif isinstance(b, Wrap):
                out.append(wrap_fig(b, col_w_cm, indent_pt))
            elif isinstance(b, model.Figure):
                out.append(float_fig(b, in_flow, col_w_cm))
            elif isinstance(b, model.Table):
                tc = table_classes.get(b.klass, {})      # classe di tabella: table.classes.<nome>
                tbl = render_table(cfg, b.header, b.rows, ratios=tc.get("col_ratios") or b.ratios, aligns=b.aligns,
                                   caption=b.caption, empty_cell=tc.get("empty_cell", empty_cell),
                                   markup=tc.get("markup", True))
                if in_flow and len(b.rows) <= 20:      # tabelle brevi: fluttuano a piena larghezza
                    tbl = (f'#place(auto, scope: "parent", float: true, clearance: 12pt)[\n{tbl}\n]')
                out.append(tbl)
                out.append(f"#v({table_after}pt)" if not (in_flow and len(b.rows) <= 20) else "")
            elif isinstance(b, model.FigureGroup):
                if b.title is not None:
                    sys.exit("A figures section with a title (end_images_placement = "
                             "'figures_section') is not supported by the Typst renderer: "
                             "use 'after_item'.")
                for f in b.figures:
                    out.append(float_fig(f, in_flow, col_w_cm))
            else:
                raise TypeError(f"blocco non gestito dal renderer Typst: {b!r}")
        if flow:
            flush_flow()
    lof = volume.meta.get("list_of_figures") or {}
    if lof.get("enabled"):
        parts.append(chapter_break(cfg))
        parts.append(list_of_figures_markup(cfg, lof))
    if uses_wrap:
        parts.insert(1, '#import "@preview/wrap-it:0.1.1": wrap-content')
    return "\n\n".join(parts)


def write_and_compile(source, out_dir, out_name, compile_pdf=True, keep_typ=False):
    """Scrive il PDF in out_dir. Il .typ resta solo con keep_typ / --no-pdf, o se la compilazione fallisce."""
    out_dir.mkdir(parents=True, exist_ok=True)
    if not compile_pdf:
        typ_path = out_dir / f"{out_name}.typ"
        typ_path.write_text(source, encoding="utf-8")
        return [typ_path]
    pdf_path = out_dir / f"{out_name}.pdf"
    with tempfile.TemporaryDirectory(prefix="volumen-typ-") as tmp:
        typ_path = Path(tmp) / f"{out_name}.typ"
        typ_path.write_text(source, encoding="utf-8")
        r = subprocess.run(["typst", "compile", "--root", "/", str(typ_path), str(pdf_path)])
        if r.returncode != 0:
            kept = out_dir / typ_path.name
            kept.write_text(source, encoding="utf-8")
            sys.exit(f"Typst compilation failed (see errors above). Source: {kept}")
    if model.ANNOT["enabled"] and model.ANNOT["items"]:
        from .. import annotate
        annotate.annotate_pdf(pdf_path, model.ANNOT)
    written = [pdf_path]
    if keep_typ:
        kept = out_dir / f"{out_name}.typ"
        kept.write_text(source, encoding="utf-8")
        written.insert(0, kept)
    return written
