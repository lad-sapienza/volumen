"""Sorgenti dei capitoli. Ogni sorgente produce un Chapter (lista di blocchi del modello)."""
from pathlib import Path


def resolve_path(value, ch, base_dir, root_key=None):
    """Percorso da volume.md: espande {id}, {images_dir}, {markdown_dir} e '~'.
    Se e' relativo lo risolve rispetto a sources.<root_key> (se dato e definito),
    altrimenti rispetto alla cartella di volume.md."""
    src = ch.get("sources", {})
    fmt = {"id": ch.get("id", ""), **{k: v for k, v in src.items()}}
    p = Path(str(value).format(**fmt)).expanduser()
    if p.is_absolute():
        return p
    root = src.get(root_key) if root_key else None
    root = Path(str(root).format(**fmt)).expanduser() if root else base_dir
    return (root if root.is_absolute() else base_dir / root) / p
