"""Annotazioni PDF: ancora i commenti CriticMarkup ai marcatori invisibili lasciati da Typst."""
import re

import fitz  # PyMuPDF


def plain(text):
    """Testo visibile di un passo annotato: toglie il markup inline."""
    t = re.sub(r"\{~~(.*?)~>(.*?)~~\}", r"\1 \2", text)       # con --annotations si vedono sia il vecchio sia il nuovo
    t = re.sub(r"\{\+\+(.*?)\+\+\}|\{--(.*?)--\}", lambda m: m.group(1) or m.group(2), t)
    t = re.sub(r"\{==|==\}|\{(?:[A-Za-z_]+=\"[^\"\n]*\"\s*)*>>.*?<<\}", "", t)
    t = re.sub(r"\[([^\]]*)\]\{\.mark\}", r"\1", t)
    return re.sub(r"[*_~^=]{1,2}", "", t).strip()


def _words(doc):
    """Parole di tutto il PDF in ordine di lettura: (pagina, rect, testo)."""
    return [(p.number, fitz.Rect(w[:4]), w[4]) for p in doc for w in p.get_text("words")]


def _pdfdoc(doc, a, text):
    """Contents come stringa PDFDocEncoding (come i PDF scritti da Acrobat) quando il testo sta in Latin-1:
    PyMuPDF userebbe UTF-16 appena c'e' una lettera accentata, che Anteprima non mostra sempre."""
    if all(ord(c) < 0x100 and not 0x7F <= ord(c) < 0xA0 for c in text):
        esc = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        esc = esc.replace("\r", "").replace("\n", "\\n")
        esc = "".join(f"\\{ord(c):03o}" if ord(c) > 0x7F else c for c in esc)   # PyMuPDF scriverebbe i byte UTF-8
        doc.xref_set_key(a.xref, "Contents", f"({esc})")


def _popup(page, a, rect):
    """Annotazione Popup collegata (senza, Anteprima non mostra la nota di un'evidenziazione)."""
    r = page.rect
    y = min(max(rect.y0, r.y0 + 10), r.y1 - 110)
    a.set_popup(fitz.Rect(r.x1 - 210, y, r.x1 - 10, y + 100))
    a.set_open(False)
    popup = a.popup_xref if hasattr(a, "popup_xref") else int(a.parent.parent.xref_get_key(a.xref, "Popup")[1].split()[0])
    # senza /P il popup non e' legato a una pagina e Anteprima lo mostra su tutte, nella stessa posizione
    page.parent.xref_set_key(popup, "P", f"{page.xref} 0 R")


def annotate_pdf(path, annot):
    doc = fitz.open(path)
    words = _words(doc)
    found = []                                        # (voce, pagina, rect marcatore, [(pagina, rect parola)])
    for it in annot["items"]:
        i = next((k for k, w in enumerate(words) if it["tag"] in w[2]), None)
        if i is None:
            print(f"Annotation not anchored (marker missing): {it['comment'][:50]}")
            continue
        target = plain(it["text"]).split() if it["text"] else []
        pno, rect, txt = words[i]
        span = []
        if target:
            rest = txt.split(it["tag"], 1)[1]          # marcatore attaccato alla prima parola
            span = [(pno, rect)] if rest else []
            n = len(target) - (1 if rest else 0)
            span += [(w[0], w[1]) for w in words[i + 1:i + 1 + n]]
        found.append((it, pno, rect, span))
    for it, pno, rect, span in found:                 # via i marcatori (testo bianco da 0,1 pt)
        doc[pno].add_redact_annot(fitz.Rect(rect.x0, rect.y0, rect.x0 + 0.1 * 7, rect.y1))
    for page in doc:
        page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE, graphics=fitz.PDF_REDACT_LINE_ART_NONE)
    rgb = tuple(int(annot["color"][i:i + 2], 16) / 255 for i in (0, 2, 4))
    for it, pno, rect, span in found:
        if span:
            a = None
            for pn in sorted({s[0] for s in span}):    # un'evidenziazione per pagina toccata
                page = doc[pn]
                a = page.add_highlight_annot(quads=[s[1].quad for s in span if s[0] == pn])
                a.set_colors(stroke=rgb)
                a.set_info(content=it["comment"], title=annot["author"])
                a.update()
                _popup(page, a, fitz.Rect(span[0][1]))
                _pdfdoc(doc, a, it["comment"])
        else:
            page = doc[pno]
            # icona nel margine destro, all'altezza del punto: non copre il testo
            a = page.add_text_annot(fitz.Point(page.rect.x1 - 28, rect.y0), it["comment"])
            a.set_info(content=it["comment"], title=annot["author"])
            a.update()
            _popup(page, a, rect)
            _pdfdoc(doc, a, it["comment"])
    doc.saveIncr()
    doc.close()


def restore_popups(path):
    """Ghostscript (--shrink) tiene le annotazioni ma butta i Popup: senza, Anteprima non mostra le note.
    Li ricrea per ogni evidenziazione/nota che ne e' priva."""
    doc = fitz.open(path)
    n = 0
    for page in doc:
        for a in page.annots(types=(fitz.PDF_ANNOT_HIGHLIGHT, fitz.PDF_ANNOT_TEXT)):
            if not a.has_popup and a.info.get("content"):
                _popup(page, a, a.rect)
                n += 1
    if n:
        doc.saveIncr()
    doc.close()
    return n
