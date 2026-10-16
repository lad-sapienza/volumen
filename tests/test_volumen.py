"""Test del motore. Esecuzione: python3 -m unittest discover -s tests -v

Il volume di prova sta in tests/fixtures/mini (copiato in una cartella temporanea, con le immagini generate al volo).
Il sorgente Typst prodotto si confronta con tests/golden/mini.typ; per aggiornarlo dopo una modifica voluta:
    UPDATE_GOLDEN=1 python3 -m unittest discover -s tests
Il PDF vero si compila solo con VOLUMEN_TEST_COMPILE=1 (serve typst e, la prima volta, la rete per il pacchetto wrap-it)."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "mini"
GOLDEN = Path(__file__).resolve().parent / "golden" / "mini.typ"
sys.path.insert(0, str(ROOT))

HAVE_PANDOC = shutil.which("pandoc") is not None


def make_images(folder, names):
    from PIL import Image
    for i, name in enumerate(names):
        Image.new("RGB", (120, 80), (40 * (i + 1) % 256, 90, 160)).save(folder / name)


class Project:
    """Una copia temporanea del volume di prova, pronta per essere impaginata."""

    def __init__(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="volumen-test-"))
        self.root = self.tmp / "mini"
        shutil.copytree(FIXTURE, self.root)
        md = self.root / "md"
        make_images(md, ["pic-a.png", "pic-b.png"])
        make_images(md / "cards", ["A-1-plan.png", "A-1-end.png"])
        self.note = md / "volume.md"
        self.out = self.tmp / "out"

    def run(self, *args, check=True):
        proc = subprocess.run([sys.executable, "-m", "volumen", "--volume", str(self.note), "--out", str(self.out), *args],
                              cwd=ROOT, capture_output=True, text=True, env={**os.environ, "VOLUMEN_NOTE": ""})
        if check and proc.returncode != 0:
            raise AssertionError(f"volumen {' '.join(args)} -> {proc.returncode}\n{proc.stderr}")
        return proc

    def cleanup(self):
        shutil.rmtree(self.tmp, ignore_errors=True)


class VolumeNote(unittest.TestCase):
    def setUp(self):
        self.p = Project()
        self.addCleanup(self.p.cleanup)

    def load(self):
        from volumen.volume_note import load_volume_note
        return load_volume_note(self.p.note)

    def test_ids_from_position_and_explicit_id(self):
        vol, warnings = self.load()
        ids = [c["id"] for c in vol["chapters"]]
        self.assertEqual(ids, ["preface", "1", "2", "3"])           # id non numerico: non avanza la numerazione
        self.assertEqual([c["id"] for c in vol["chapters"][2]["chapters"]], ["2.1", "2.2"])
        self.assertEqual(warnings, [])

    def test_container_folder_and_options(self):
        vol, _ = self.load()
        part = vol["chapters"][2]
        self.assertTrue(part["divider"])
        self.assertEqual(part["title"], "Parte seconda")
        beta, cards = part["chapters"]
        self.assertEqual(beta["columns"], 2)
        self.assertEqual((cards["source"], cards["dir"]), ("folder", "cards"))
        self.assertEqual(cards["series_order"], ["A", "B"])
        self.assertEqual(cards["first"], ["B-1"])
        self.assertIs(cards["page_break_per_item"], True)
        self.assertFalse(vol["chapters"][3]["bibliography"])

    def test_frontmatter_is_flattened(self):
        vol, _ = self.load()
        self.assertEqual(vol["toc"], {"enabled": True, "depth": 2})
        self.assertEqual(vol["list_of_figures"], {"enabled": True})
        self.assertEqual(vol["output"], {"name": "mini"})
        self.assertEqual(vol["authors"][0], {"name": "Ada Autrice", "affiliation": "Università di Prova"})
        self.assertEqual(vol["authors"][1], {"name": "Bruno Autore"})
        self.assertEqual(vol["sources"]["bibliography"], "../bib/refs.bib")
        self.assertEqual(Path(vol["frontmatter"][0]).name, "front.md")

    def test_style_blocks_are_config_and_lists_inside_are_not_chapters(self):
        vol, _ = self.load()
        cfg = vol["_config"]
        self.assertEqual(cfg["page"]["margin_interior"], 3.5)
        self.assertEqual(cfg["images"]["classes"]["plan"]["width_pct"], 80)
        text = self.p.note.read_text()
        self.p.note.write_text(text.replace("```yaml\n", "```yaml\nlista:\n  - uno\n  - due\n"))
        vol2, _ = self.load()
        self.assertEqual(len(vol2["chapters"]), 4)                   # le voci `- ` del blocco non sono capitoli
        self.assertEqual(vol2["_config"]["lista"], ["uno", "due"])

    def test_missing_file_and_untitled_chapter_are_reported(self):
        self.p.note.write_text(self.p.note.read_text().replace("- [gamma](gamma.md)", "- [manca](manca.md)\n- [gamma](gamma.md)"))
        (self.p.root / "md" / "gamma.md").write_text("Senza titolo nel frontmatter.\n")
        _, warnings = self.load()
        kinds = {w[1] for w in warnings}
        self.assertIn("file non trovato", kinds)
        self.assertIn("il file non ha `title` nel frontmatter", kinds)

    def test_invalid_yaml_stops_with_line_number(self):
        self.p.note.write_text(self.p.note.read_text().replace("page: {size: A4,", "page: [size: A4,"))
        with self.assertRaises(SystemExit) as cm:
            self.load()
        self.assertIn("YAML non valido", str(cm.exception))
        self.assertIn("riga", str(cm.exception))

    def test_markdown_and_wiki_links_are_equivalent(self):
        self.p.note.write_text(self.p.note.read_text().replace("- [alfa](alfa.md)", "- [[alfa]]"))
        vol, _ = self.load()
        self.assertEqual(Path(vol["chapters"][1]["file"]).name, "alfa.md")


class Config(unittest.TestCase):
    def test_layers_blocks_then_set(self):
        from types import SimpleNamespace
        from volumen.config import load_config
        args = SimpleNamespace(config=None, set=["styles.normal.size=9", "page.size=Letter"])
        cfg = load_config(args, {"styles": {"normal": {"size": 11, "font": "X"}}, "page": {"size": "A4"}})
        self.assertEqual(cfg["styles"]["normal"], {"size": 9, "font": "X"})
        self.assertEqual(cfg["page"]["size"], "Letter")

    def test_empty_config_has_code_defaults(self):
        from volumen.config import style_cfg
        sc = style_cfg({}, "normal")
        self.assertEqual((sc["font"], sc["size"], sc["line_height"]), ("Libertinus Serif", 11, 13.2))


class Engine(unittest.TestCase):
    def setUp(self):
        self.p = Project()
        self.addCleanup(self.p.cleanup)

    def json(self, *args):
        proc = self.p.run("--json", *args)
        lines = proc.stdout.strip().splitlines()
        self.assertEqual(len(lines), 1, f"stdout deve contenere solo il JSON, non: {proc.stdout!r}")
        return json.loads(lines[0])

    def test_list_chapters_json(self):
        data = self.json("--list-chapters")
        rows = {r["id"]: r for r in data["chapters"]}
        self.assertEqual(list(rows)[:3], ["preface", "1", "2"])
        self.assertEqual(rows["1"]["title"], "Primo capitolo")              # il titolo viene dal file
        self.assertEqual(rows["2.2"]["source"], "folder")
        self.assertEqual(rows["2.2"]["dir"], "cards")

    @unittest.skipUnless(HAVE_PANDOC, "serve pandoc")
    def test_validate_reports_without_rendering(self):
        data = self.json("--validate")
        self.assertTrue(data["validate"])
        self.assertEqual(data["n_included"], 3)                             # A-1, A-2, B-1 (Z-9 e' escluso)
        self.assertEqual(data["n_excluded"], 1)
        self.assertTrue(Path(data["anomalies"]).exists())
        self.assertFalse(list(self.p.out.glob("*.typ")) + list(self.p.out.glob("*.pdf")))

    @unittest.skipUnless(HAVE_PANDOC, "serve pandoc")
    def test_build_typ_json_contract(self):
        data = self.json("--no-pdf", "--keep-typ")
        self.assertTrue(data["ok"])
        self.assertTrue(data["typ"].endswith("mini.typ"))
        self.assertIsNone(data["pdf"])
        self.assertEqual(data["n_included"], 3)

    def test_unknown_volume_fails_with_message(self):
        proc = subprocess.run([sys.executable, "-m", "volumen", "--volume", str(self.p.tmp / "no.md")], cwd=ROOT,
                              capture_output=True, text=True)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("Nota del volume non trovata", proc.stderr)

    @unittest.skipUnless(HAVE_PANDOC, "serve pandoc")
    def test_typst_source_matches_golden(self):
        data = self.json("--no-pdf", "--keep-typ")
        text = Path(data["typ"]).read_text(encoding="utf-8")
        for root in (str(self.p.root.resolve()), str(self.p.root)):      # /private/var/... prima di /var/...
            text = text.replace(root, "@ROOT@")
        if os.environ.get("UPDATE_GOLDEN"):
            GOLDEN.parent.mkdir(exist_ok=True)
            GOLDEN.write_text(text, encoding="utf-8")
        self.assertTrue(GOLDEN.exists(), "manca tests/golden/mini.typ (UPDATE_GOLDEN=1 per crearlo)")
        self.assertEqual(text, GOLDEN.read_text(encoding="utf-8"))

    @unittest.skipUnless(HAVE_PANDOC, "serve pandoc")
    def test_features_in_typst_source(self):
        data = self.json("--no-pdf", "--keep-typ", "--annotations")
        text = Path(data["typ"]).read_text(encoding="utf-8")
        self.assertIn("Fig. 1.1", text)                                    # numerazione figure per capitolo
        self.assertIn("Table 1.1", text)
        self.assertIn("Rossi", text)                                       # citazione risolta
        self.assertIn("wrap-content", text)                                # figura con testo intorno
        self.assertIn("A-1", text)

    def test_inline_highlight_and_attribute_comments(self):
        from volumen import model
        from volumen.render.typst import md_inline_to_typst as f
        out = f('**==Fig==** e ==a = b== {date="2026-10-06">>nota<<}fine')
        self.assertNotIn("==", out)                                        # evidenziato anche con = dentro e nel grassetto
        self.assertIn("a = b", out)
        self.assertNotIn("nota", out)                                      # commento con attributi: sparisce senza --annotations
        self.assertIn("fine", out)
        self.assertEqual(model.critic_parts('{date="x">>c<<}'), ("", "c"))

    @unittest.skipUnless(HAVE_PANDOC, "serve pandoc")
    def test_docx_builds_and_keeps_chapter_link_inside_footnote(self):
        # regressione: un link a capitolo dentro una nota mandava add_md_runs in ricorsione infinita
        data = self.json("--format", "docx")
        with zipfile.ZipFile(data["docx"]) as z:
            doc = z.read("word/document.xml").decode("utf-8")
            notes = z.read("word/footnotes.xml").decode("utf-8")
        self.assertIn("Primo capitolo", doc)
        self.assertIn("Nota con un link al", notes)
        self.assertIn("capitolo beta", notes) if "capitolo beta" in notes else self.assertIn("2.1", notes)

    @unittest.skipUnless(HAVE_PANDOC, "serve pandoc")
    def test_chapter_selection_builds_only_that_chapter(self):
        data = self.json("--no-pdf", "--keep-typ", "--chapter", "3")
        text = Path(data["typ"]).read_text(encoding="utf-8")
        self.assertIn("Fine del volume", text)
        self.assertNotIn("Il sito fu abitato", text)

    @unittest.skipUnless(os.environ.get("VOLUMEN_TEST_COMPILE") and shutil.which("typst"), "VOLUMEN_TEST_COMPILE=1 e typst")
    def test_pdf_compiles(self):
        data = self.json()
        self.assertTrue(Path(data["pdf"]).stat().st_size > 1000)


if __name__ == "__main__":
    unittest.main()
