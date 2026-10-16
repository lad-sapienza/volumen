"""Paragrafi con stile personalizzato: `::: {.nome font="Minion Pro" size=28 weight=bold align=center margin-top=6cm}`.

Gli attributi si risolvono qui (una volta sola) in un dizionario di stile con le stesse chiavi di
lo stile (`volume.md`, sezione «Stile») → `styles`; i renderer Typst e Word lo applicano al blocco."""
import re

from .config import style_cfg

ATTR = re.compile(r'([\w-]+)=("[^"]*"|\'[^\']*\'|\S+)')
CLASS = re.compile(r"(?:^|\s)\.([\w-]+)")
UNITS_PT = {"pt": 1.0, "cm": 72 / 2.54, "mm": 72 / 25.4, "in": 72.0, "px": 0.75}
ALIGNS = {"left", "center", "right", "justify"}
CASES = {"upper", "lower", "smallcaps"}


def parse_attrs(text):
    """'{.titolo size=28 align=center}' -> (['titolo'], {'size': '28', 'align': 'center'})."""
    inner = (text or "").strip().strip("{}")
    attrs = {k: v.strip("\"'") for k, v in ATTR.findall(inner)}
    return CLASS.findall(ATTR.sub("", inner)), attrs


def length_pt(spec, size=None):
    """'6cm', '12pt', '1.5em', '10' (pt) -> punti; None se non valido."""
    m = re.fullmatch(r"\s*(-?[0-9]*\.?[0-9]+)\s*(cm|mm|in|pt|px|em)?\s*", str(spec))
    if not m:
        return None
    v, unit = float(m.group(1)), m.group(2) or "pt"
    if unit == "em":
        return v * (size or 11)
    return v * UNITS_PT[unit]


def resolve(cfg, classes, attrs, warn=None):
    """-> stile (dict). Base: lo stile con nome (primo `.nome` definito in config `styles`), altrimenti
    `normal` senza rientro, allineato a sinistra e senza spazi. Gli attributi lo modificano."""
    warn = warn or (lambda msg: None)
    named = next((c for c in classes if c in cfg.get("styles", {})), None)
    for c in classes:
        if c != named and c not in cfg.get("styles", {}):
            warn(f"style `.{c}` not defined in the style of volume.md (styles)")
    if named:
        sc = style_cfg(cfg, named, fallback="normal")
    else:
        sc = style_cfg(cfg, "normal")
        sc.update(first_line_indent=0, space_before=0, space_after=0, align="left", indent_left=0, indent_right=0)
    sc = dict(sc)
    sc.setdefault("tracking", 0)
    sc.setdefault("case", None)
    size_set = False
    for k, v in attrs.items():
        key = k.replace("_", "-").lower()
        if key == "font":
            sc["font"] = v
        elif key == "size":
            n = length_pt(v)
            if n:
                sc["size"], size_set = n, True
        elif key == "weight":
            sc["bold"] = v.lower() == "bold" or (v.isdigit() and int(v) >= 600)
        elif key == "italic":
            sc["italic"] = v.lower() in ("1", "true", "yes", "italic")
        elif key == "color":
            sc["color"] = v.lstrip("#").upper()
        elif key == "align":
            if v in ALIGNS:
                sc["align"] = v
            else:
                warn(f"invalid align: {v} (left|center|right|justify)")
        elif key in ("margin-top", "space-before"):
            n = length_pt(v, sc["size"])
            sc["space_before"] = n if n is not None else sc["space_before"]
        elif key in ("margin-bottom", "space-after"):
            n = length_pt(v, sc["size"])
            sc["space_after"] = n if n is not None else sc["space_after"]
        elif key == "line-height":
            n = length_pt(v, sc["size"])
            if n:
                sc["line_height"] = n
        elif key == "indent":
            n = length_pt(v, sc["size"])
            sc["first_line_indent"] = n if n is not None else sc["first_line_indent"]
        elif key == "tracking":
            n = length_pt(v, sc["size"])
            sc["tracking"] = n if n is not None else 0
        elif key == "width":
            if re.fullmatch(r"\s*[0-9]*\.?[0-9]+\s*(cm|mm|in|pt|px|%)?\s*", v):
                sc["width"] = v.strip()      # senza unita' = cm (come per le immagini); % della larghezza utile
            else:
                warn(f"invalid width: {v} (e.g. 8cm, 60%)")
        elif key == "case":
            if v in CASES:
                sc["case"] = v
            else:
                warn(f"invalid case: {v} (upper|lower|smallcaps)")
        else:
            warn(f"unknown attribute: {k}")
    if size_set and "line-height" not in {k.replace("_", "-").lower() for k in attrs}:
        sc["line_height"] = round(sc["size"] * 1.2, 1)       # interlinea proporzionale alla nuova corpo
    return sc
