"""Configurazione: stile e composizione dalla nota del volume (volume.md); i valori mancanti usano i default del codice."""
import json
import sys
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent.parent   # radice del progetto


DEFAULT_STYLE = {
    "font": "Libertinus Serif", "size": 11, "bold": False, "italic": False, "color": "000000",
    "line_height": None, "first_line_indent": 0, "indent_left": 0, "indent_right": 0, "space_before": 0, "space_after": 0, "align": "left",  # line_height in pt (None = corpo * 1.2)
}


def deep_merge(base, over):
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            deep_merge(base[k], v)
        else:
            base[k] = v
    return base


def set_path(cfg, dotted, raw):
    keys = dotted.split(".")
    try:
        val = json.loads(raw)
    except json.JSONDecodeError:
        val = raw
    node = cfg
    for k in keys[:-1]:
        node = node.setdefault(k, {})
    node[keys[-1]] = val


def load_config(args, overrides=None):
    """Impostazioni di grafica/layout. Strati, dal piu' basso: blocchi ```yaml della nota del volume (`overrides`),
    --config (file JSON/YAML opzionale), --set. Nessuna chiave e' obbligatoria: ogni valore ha un default nel codice."""
    cfg = deep_merge({}, overrides or {})
    if args.config:
        extra = Path(args.config).expanduser()
        deep_merge(cfg, yaml.safe_load(extra.read_text(encoding="utf-8")) or {})    # il JSON e' YAML valido
    for item in args.set or []:
        if "=" not in item:
            sys.exit(f"--set richiede chiave=valore, ricevuto: {item}")
        k, v = item.split("=", 1)
        set_path(cfg, k.strip(), v.strip())
    return cfg


def style_cfg(cfg, name, fallback=None):
    """Stile <name>; se non definito in config usa quello di <fallback> (es. quote -> normal)."""
    styles = cfg.get("styles", {})
    src = styles.get(name) or (styles.get(fallback) if fallback else None) or {}
    sc = {**DEFAULT_STYLE, **src}
    if sc.get("line_height") is None:
        sc["line_height"] = round(sc["size"] * 1.2, 1)
    return sc


def heading_style(cfg, level):
    """Stile per h<level> (fino a h5): se non definito in config usa il livello
    definito piu' vicino sopra (h4 assente -> h3, ecc.)."""
    styles = cfg.get("styles", {})
    for n in range(min(level, 5), 0, -1):
        if f"h{n}" in styles:
            return f"h{n}"
    return "h1"
