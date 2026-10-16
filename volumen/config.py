"""Configuration: style and composition from the volume note (volume.md); missing values use the defaults of the code."""
import json
import sys
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent.parent   # root of the project


DEFAULT_STYLE = {
    "font": "Libertinus Serif", "size": 11, "bold": False, "italic": False, "color": "000000",
    "line_height": None, "first_line_indent": 0, "indent_left": 0, "indent_right": 0, "space_before": 0, "space_after": 0, "align": "left",  # line_height in pt (None = size * 1.2)
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
    """Graphics/layout settings. Layers, from the lowest: ```yaml blocks of the volume note (`overrides`),
    --config (optional JSON/YAML file), --set. No key is required: every value has a default in the code."""
    cfg = deep_merge({}, overrides or {})
    if args.config:
        extra = Path(args.config).expanduser()
        deep_merge(cfg, yaml.safe_load(extra.read_text(encoding="utf-8")) or {})    # JSON is valid YAML
    for item in args.set or []:
        if "=" not in item:
            sys.exit(f"--set requires key=value, got: {item}")
        k, v = item.split("=", 1)
        set_path(cfg, k.strip(), v.strip())
    return cfg


def style_cfg(cfg, name, fallback=None):
    """Style <name>; if not defined in config it uses that of <fallback> (e.g. quote -> normal)."""
    styles = cfg.get("styles", {})
    src = styles.get(name) or (styles.get(fallback) if fallback else None) or {}
    sc = {**DEFAULT_STYLE, **src}
    if sc.get("line_height") is None:
        sc["line_height"] = round(sc["size"] * 1.2, 1)
    return sc


def heading_style(cfg, level):
    """Style for h<level> (up to h5): if not defined in config it uses the nearest level
    defined above (h4 missing -> h3, etc.)."""
    styles = cfg.get("styles", {})
    for n in range(min(level, 5), 0, -1):
        if f"h{n}" in styles:
            return f"h{n}"
    return "h1"
