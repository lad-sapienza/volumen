"""Anomalie e report (anomalie.md / anomalie.csv)."""
import csv
import re
from collections import Counter


def natural_key(cid):
    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", cid)]


class Anomalies:
    def __init__(self):
        self.rows = []  # (id, kind, field, detail)
        self._seen = set()

    def add(self, cid, kind, field, detail):
        row = (cid, kind, field, detail)
        if row not in self._seen:
            self._seen.add(row)
            self.rows.append(row)

    def counts(self):
        return Counter(r[1] for r in self.rows)


SOURCES_NOTE = "Lo script non corregge testi e dati: le correzioni vanno fatte nelle fonti (file Markdown, immagini, bibliografia)."


def write_reports(an, excluded, out_dir, stats, name="anomalie", title="Anomalie rilevate", note=SOURCES_NOTE):
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = sorted(an.rows, key=lambda r: (natural_key(r[0]), r[1], r[2]))
    with open(out_dir / f"{name}.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, quoting=csv.QUOTE_ALL)
        w.writerow(["id", "tipo", "campo", "dettaglio"])
        w.writerows(rows)

    counts = an.counts()
    lines = [f"# {title}", "",
             f"Voci nel documento: {stats['n_included']}  ·  "
             f"escluse: {len(excluded)}  ·  anomalie: {len(rows)}", "",
             note, "",
             "## Riepilogo per tipo", "", "| Tipo | N |", "|---|---:|"]
    for k, n in counts.most_common():
        lines.append(f"| {k} | {n} |")
    lines += ["", "## Dettaglio per voce", ""]
    cur = None
    for cid, kind, field, detail in rows:
        if cid != cur:
            lines += ["", f"### {cid}", ""]
            cur = cid
        lines.append(f"- **{kind}** ({field}): {detail}")
    if excluded:
        lines += ["", "## Record esclusi", ""]
        for cid, reason in sorted(excluded, key=lambda t: natural_key(t[0])):
            lines.append(f"- {cid}: {reason}")
    (out_dir / f"{name}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
