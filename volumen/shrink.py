"""Reduces a PDF with Ghostscript (same recipe as the `shrink-pdf` script): images resampled,
vector content intact. Suitable for drafts to send around, not for print."""
import shutil
import subprocess
import sys
from pathlib import Path

PRESETS = ("screen", "ebook", "printer")     # screen = 72 dpi (smallest), ebook = 150 dpi, printer = 300 dpi


def shrink_pdf(src, dst=None, preset="screen"):
    """Writes `<src>-shrink.pdf` (or dst) and returns it; the original stays as it is."""
    src = Path(src)
    dst = Path(dst) if dst else src.with_name(f"{src.stem}-shrink.pdf")
    if not shutil.which("gs"):
        sys.exit("--shrink needs Ghostscript (gs): brew install ghostscript")
    r = subprocess.run(
        ["gs", "-dBATCH", "-dNOPAUSE", "-q", "-sDEVICE=pdfwrite", f"-dPDFSETTINGS=/{preset}",
         "-dColorImageDownsampleType=/Bicubic", "-dGrayImageDownsampleType=/Bicubic",
         "-dMonoImageDownsampleType=/Subsample", f"-sOutputFile={dst}", str(src)])
    if r.returncode != 0:
        sys.exit("Ghostscript failed (see errors above).")
    from . import annotate
    annotate.restore_popups(dst)          # gs drops the annotation Popups (--annotations)
    return dst


def mb(path):
    return Path(path).stat().st_size / 1e6
