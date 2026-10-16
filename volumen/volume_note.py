"""Volume note (`volume.md`): composition = flat frontmatter + nested list of links to the chapters.

    ---
    title: Volume title
    authors: ["First Last | Affiliation"]
    toc: true
    toc_depth: 2
    bibliography: ../bib/book.bib
    ---
    - [preface](preface.md) {id=preface}                 # explicit non-numeric id: outside the numbering
    - [project](project.md)
    - Archaeology of the site {divider}        # entry without a file with children = container (divider page)
      - [introduction](introduction.md)
      - Complexes catalogue {source=complexes series_order=F1,F2}   # source=<folder of Markdown files>

    ## Style
    ```yaml
    page: {size: A4}
    styles: {normal: {font: Minion Pro, size: 11}}
    ```

A chapter's title comes ONLY from the `title` of its file. The graphics are in the ```yaml blocks of the same note ("Style" section).
The result is the same dictionary that used to be read from volume.md."""
import re
import sys
from pathlib import Path
from urllib.parse import unquote

import yaml

from .config import deep_merge
from .sources import markdown

WIKILINK = re.compile(r"^\[\[([^\]]+)\]\]$")
MDLINK = re.compile(r"^\[[^\]]*\]\(<?([^)<>]+?)>?\)$")
ITEM = re.compile(r"^(\s*)[-*+]\s+(.*\S)\s*$")
ATTRS = re.compile(r"^(.*?)\s*\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}\s*$")      # text {attributes} (nested braces allowed: {id})
ATTR = re.compile(r'([\w-]+)(?:=("[^"]*"|\'[^\']*\'|\S+))?')
LIST_KEYS = {"series_order", "exclude_prefixes", "first", "exclude", "include", "authors"}

# flat frontmatter keys -> position in the nested dictionary (prefix_key -> prefix.key)
GROUPS = ("toc", "list_of_figures", "output")
SOURCE_KEYS = ("images_dir", "bibliography", "csl", "markdown_dir")


def _value(key, raw):
    """Value of a `key=value` attribute (without a value = true)."""
    if not raw:
        return True
    quoted = raw[0] in "\"'"
    v = raw.strip("\"'")
    if key in LIST_KEYS:
        return [x.strip() for x in v.split(",") if x.strip()]
    if not quoted:
        if v.lower() in ("true", "false"):
            return v.lower() == "true"
        if re.fullmatch(r"-?\d+", v):
            return int(v)
        if re.fullmatch(r"-?\d*\.\d+", v):
            return float(v)
    return v


def parse_attrs(text):
    return {k.replace("-", "_"): _value(k.replace("-", "_"), v) for k, v in ATTR.findall(text)}


class _Resolver:
    """Resolves `[text](path.md)` / `[[name]]` to a file: first relative to the note's folder, then by
    name in the whole vault (the nearest folder with `.obsidian`, otherwise the note's folder)."""

    def __init__(self, base_dir):
        self.base = base_dir
        self.root = next((p for p in [base_dir, *base_dir.parents] if (p / ".obsidian").is_dir()), base_dir)
        self._index = None

    def target(self, raw):
        """Text of a link -> path (without anchor, alias and extension) or None."""
        raw = raw.strip()
        m = WIKILINK.match(raw)
        if m:
            t = m.group(1)
        else:
            m = MDLINK.match(raw)
            if not m:
                return None
            t = unquote(m.group(1))
        t = t.split("|", 1)[0].split("#", 1)[0].strip()
        return re.sub(r"\.md$", "", t) or None

    def find(self, name):
        direct = (self.base / f"{name}.md")
        if direct.is_file():
            return direct.resolve(), None
        if self._index is None:
            self._index = {}
            for f in sorted(self.root.rglob("*.md")):
                self._index.setdefault(f.stem, []).append(f)
        found = self._index.get(Path(name).stem, [])
        if not found:
            return None, "file not found"
        return found[0].resolve(), (f"ambiguous name ({len(found)} files): used {found[0]}" if len(found) > 1 else None)


def _frontmatter(meta):
    """Flat frontmatter -> volume dictionary (toc_depth -> toc.depth, authors 'Name | Affiliation', ...)."""
    vol = {}
    for k, v in meta.items():
        group = next((g for g in GROUPS if k == g or k.startswith(g + "_")), None)
        if group and k == group:
            if isinstance(v, dict):
                vol.setdefault(group, {}).update(v)
            elif group == "output":
                vol.setdefault(group, {})["name"] = v
            else:
                vol.setdefault(group, {})["enabled"] = bool(v)
        elif group:
            vol.setdefault(group, {})[k[len(group) + 1:]] = v
        elif k in SOURCE_KEYS:
            vol.setdefault("sources", {})[k] = v
        elif k == "authors":
            items = v if isinstance(v, list) else [v]
            vol["authors"] = [a if isinstance(a, dict) else
                              {k2: v2 for k2, v2 in zip(("name", "affiliation"), (x.strip() for x in str(a).split("|", 1)))}
                              for a in items]
        else:
            vol[k] = v
    return vol


def _flat(values):
    for v in values or []:
        if isinstance(v, list):
            yield from _flat(v)
        else:
            yield v


def load_volume_note(path):
    """-> (volume dictionary, [(id, type, field, detail)] composition anomalies)."""
    path = Path(path)
    meta, body = markdown.split_frontmatter(path.read_text(encoding="utf-8"))
    base = path.resolve().parent
    res = _Resolver(base)
    warnings = []
    vol = _frontmatter(meta or {})
    vol.pop("type", None)

    def link_file(raw, where):
        name = res.target(str(raw))
        if name is None:
            name = re.sub(r"\.md$", "", str(raw).strip())      # simple name (e.g. title-page.md)
        f, warn = res.find(name)
        if f is None:
            warnings.append((where, "file not found", "volume.md", str(raw)))
            return None
        if warn:
            warnings.append((where, warn, "volume.md", str(raw)))
        return str(f)

    if "frontmatter" in vol:
        files = [link_file(x, "frontmatter") for x in _flat(vol["frontmatter"])]
        vol["frontmatter"] = [f for f in files if f]

    # --- the body: list of chapters (entries outside the code blocks) + ```yaml blocks = style/configuration
    items, config = [], {}
    fence, info, block, start = None, "", [], 0
    for n, ln in enumerate(body.replace("\t", "    ").splitlines(), 1):
        s = ln.strip()
        if fence is None:
            if s.startswith(("```", "~~~")):
                fence, info, block, start = s[:3], s[3:].strip().split(" ")[0].lower(), [], n
                continue
            m = ITEM.match(ln)
            if m:
                items.append((len(m.group(1)), m.group(2)))
        elif s.startswith(fence):
            if info in ("yaml", "yml"):
                try:
                    data = yaml.safe_load("\n".join(block)) or {}
                except yaml.YAMLError as e:
                    mark = getattr(e, "problem_mark", None)
                    where = f"body line {start + 1 + mark.line}" if mark else f"block at line {start}"
                    sys.exit(f"{path.name}: invalid YAML ({where}): {getattr(e, 'problem', e)}")
                if not isinstance(data, dict):
                    sys.exit(f"{path.name}: the yaml block at body line {start} must be a key: value map")
                deep_merge(config, data)
            fence = None
        else:
            block.append(ln)
    vol["_config"] = config

    def build(pos, indent, parent_id):
        """Entries at the same level starting from `pos`. -> (chapters, new position)."""
        out, counter = [], 0
        while pos < len(items) and items[pos][0] >= indent:
            depth, text = items[pos]
            pos += 1
            am = ATTRS.match(text)
            label, attrs = (am.group(1).strip(), parse_attrs(am.group(2))) if am else (text, {})
            explicit = attrs.pop("id", None)
            if explicit is not None:
                cid = str(explicit)
                tail = cid.rsplit(".", 1)[-1]
                if tail.isdigit():
                    counter = int(tail)              # numeric id: the numbering restarts from there
            else:
                counter += 1
                cid = f"{parent_id}.{counter}" if parent_id else str(counter)
            children = []
            if pos < len(items) and items[pos][0] > indent:
                children, pos = build(pos, items[pos][0], cid)
            name = res.target(label)
            ch = {"id": cid}
            if name:                                 # entry with a link: Markdown chapter (title = the file's title)
                if children:
                    warnings.append((cid, "an entry with a file cannot have children", "volume.md", label))
                f, warn = res.find(name)
                if f is None:
                    warnings.append((cid, "file not found", "volume.md", label))
                    continue
                if warn:
                    warnings.append((cid, warn, "volume.md", label))
                if "|" in label:
                    warnings.append((cid, "link alias ignored (the title comes from the file)", "volume.md", label))
                ch.update(source="markdown", file=str(f))
            elif "source" in attrs:                  # source=<folder>: folder of Markdown files
                if children:
                    warnings.append((cid, "a folder (source=) cannot have children", "volume.md", label))
                ch.update(title=label, dir=attrs.pop("source"), source="folder")
            elif children:                           # container
                ch.update(title=label, chapters=children)
            else:
                warnings.append((cid, "entry with neither file nor source", "volume.md", label))
                continue
            ch.update(attrs)
            out.append(ch)
        return out, pos

    vol["chapters"], _ = build(0, items[0][0] if items else 0, "")
    if not vol["chapters"]:
        warnings.append(("", "no chapters in the note", "volume.md", "a list `- [file](file.md)` is needed"))

    def check_titles(chs):
        for c in chs:
            if c.get("source") == "markdown":
                m, _ = markdown.split_frontmatter(Path(c["file"]).read_text(encoding="utf-8"))
                if not (m or {}).get("title"):
                    warnings.append((c["id"], "the file has no `title` in its frontmatter", Path(c["file"]).name,
                                     "the chapter title comes only from the file"))
            check_titles(c.get("chapters", []))
    check_titles(vol["chapters"])
    return vol, warnings
