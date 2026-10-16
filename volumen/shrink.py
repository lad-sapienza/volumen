"""Riduce un PDF con Ghostscript (stessa ricetta dello script `shrink-pdf`): immagini ricampionate,
contenuto vettoriale intatto. Adatto alle bozze da inviare, non alla stampa."""
import shutil
import subprocess
import sys
from pathlib import Path

PRESETS = ("screen", "ebook", "printer")     # screen = 72 dpi (piu' piccolo), ebook = 150 dpi, printer = 300 dpi


def shrink_pdf(src, dst=None, preset="screen"):
    """Scrive `<src>-shrink.pdf` (o dst) e lo restituisce; l'originale resta com'e'."""
    src = Path(src)
    dst = Path(dst) if dst else src.with_name(f"{src.stem}-shrink.pdf")
    if not shutil.which("gs"):
        sys.exit("--shrink richiede Ghostscript (gs): brew install ghostscript")
    r = subprocess.run(
        ["gs", "-dBATCH", "-dNOPAUSE", "-q", "-sDEVICE=pdfwrite", f"-dPDFSETTINGS=/{preset}",
         "-dColorImageDownsampleType=/Bicubic", "-dGrayImageDownsampleType=/Bicubic",
         "-dMonoImageDownsampleType=/Subsample", f"-sOutputFile={dst}", str(src)])
    if r.returncode != 0:
        sys.exit("Ghostscript ha fallito (vedi errori sopra).")
    from . import annotate
    annotate.restore_popups(dst)          # gs scarta i Popup delle annotazioni (--annotations)
    return dst


def mb(path):
    return Path(path).stat().st_size / 1e6
