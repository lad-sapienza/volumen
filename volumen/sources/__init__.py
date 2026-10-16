"""Chapter sources. Each source produces a Chapter (list of blocks of the model)."""
from pathlib import Path


def resolve_path(value, ch, base_dir, root_key=None):
    """Path from volume.md: expands {id}, {images_dir}, {markdown_dir} and '~'.
    If relative it resolves it against sources.<root_key> (if given and defined),
    otherwise against the folder of volume.md."""
    src = ch.get("sources", {})
    fmt = {"id": ch.get("id", ""), **{k: v for k, v in src.items()}}
    p = Path(str(value).format(**fmt)).expanduser()
    if p.is_absolute():
        return p
    root = src.get(root_key) if root_key else None
    root = Path(str(root).format(**fmt)).expanduser() if root else base_dir
    return (root if root.is_absolute() else base_dir / root) / p
