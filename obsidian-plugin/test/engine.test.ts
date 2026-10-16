import { test } from "node:test";
import assert from "node:assert/strict";
import * as path from "path";
import * as fs from "fs";
import * as os from "os";
import { buildArgs, chapterForFile, childEnv, detectEngineDir, findBinary, listChapters, probeEnvironment,
  pythonCandidates, runEngine, BuildResult } from "../src/engine";

const settings = { python: process.env.VOLUMEN_PYTHON || "python3", engineDir: path.resolve(__dirname, "../.."), extraPath: "/opt/homebrew/bin" };

test("buildArgs: volume, formato, capitoli, annotazioni", () => {
  assert.deepEqual(
    buildArgs({ volume: "/v/volume.md", format: "typst", chapters: ["5.2", "6"], annotations: true }),
    ["-m", "volumen", "--json", "--volume", "/v/volume.md", "--format", "typst", "--chapter", "5.2", "6", "--annotations"]);
  assert.deepEqual(buildArgs({ volume: "/v/volume.md", format: "docx" }).slice(-2), ["--format", "docx"]);
});

test("childEnv: prima il PATH indicato, poi quello ereditato, poi le cartelle note che esistono; senza duplicati", () => {
  const env = childEnv(settings, { PATH: "/usr/bin:/opt/homebrew/bin" }, (d) => d === "/opt/homebrew/bin" || d === "/Library/TeX/texbin");
  assert.equal(env.PATH, "/opt/homebrew/bin:/usr/bin:/Library/TeX/texbin");
  assert.equal(env.PYTHONUTF8, "1");
});

test("findBinary: trova un eseguibile nel PATH e ignora i file non eseguibili", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "vol-bin-"));
  fs.writeFileSync(path.join(dir, "tool"), "#!/bin/sh\n", { mode: 0o755 });
  fs.writeFileSync(path.join(dir, "noexec"), "x", { mode: 0o644 });
  assert.equal(findBinary("tool", { PATH: dir }), path.join(dir, "tool"));
  assert.equal(findBinary("noexec", { PATH: dir }), null);
  assert.equal(findBinary("assente", { PATH: dir }), null);
});

test("detectEngineDir: dal plugin (anche tramite link simbolico) risale al repo con il pacchetto volumen", () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "vol-repo-"));
  fs.mkdirSync(path.join(root, "volumen"));
  fs.writeFileSync(path.join(root, "volumen", "__init__.py"), "");
  fs.mkdirSync(path.join(root, "obsidian-plugin"));
  const link = path.join(os.tmpdir(), `vol-link-${process.pid}`);
  fs.rmSync(link, { force: true });
  fs.symlinkSync(path.join(root, "obsidian-plugin"), link);
  assert.equal(detectEngineDir(link), fs.realpathSync(root));
  assert.equal(detectEngineDir(os.tmpdir()), null);
});

test("pythonCandidates: quello indicato per primo, poi python3, nessun duplicato", () => {
  const c = pythonCandidates("/x/python3", "/nonexistent-home");
  assert.equal(c[0], "/x/python3");
  assert.equal(c[1], "python3");
  assert.equal(new Set(c).size, c.length);
  assert.ok(c.includes("/opt/homebrew/bin/python3"));
});

test("probeEnvironment: un Python indicato a mano ma inesistente non viene sostituito di nascosto", async () => {
  const r = await probeEnvironment({ python: "/non/esiste/python3", engineDir: settings.engineDir, extraPath: "" }, null);
  assert.equal(r.python, null);
  assert.equal(r.ok, false);
  assert.ok(r.problems.some((p) => /Python/.test(p)));
});

test("probeEnvironment: rilevamento automatico del motore reale", { skip: !process.env.VOLUMEN_TEST_VOLUME }, async () => {
  const r = await probeEnvironment({ python: "", engineDir: "", extraPath: "" }, path.join(settings.engineDir, "obsidian-plugin"));
  assert.equal(r.ok, true, r.problems.join("; "));
  assert.ok(r.python && r.typst && r.pandoc);
});

test("chapterForFile: file di un capitolo e file dentro una cartella source=", () => {
  const rows = [
    { id: "1", title: "A", source: "markdown", depth: 0, file: "/v/md/a.md", dir: null },
    { id: "5.2", title: "Cat", source: "folder", depth: 1, file: null, dir: "complexes" },
  ];
  assert.equal(chapterForFile(rows, "/v/md/a.md", "/v/md")?.id, "1");
  assert.equal(chapterForFile(rows, "/v/md/complexes/F1-01.md", "/v/md")?.id, "5.2");
  assert.equal(chapterForFile(rows, "/v/md/altro.md", "/v/md"), undefined);
});

// integrazione con il motore reale: serve VOLUMEN_TEST_VOLUME (percorso di volume.md)
const volume = process.env.VOLUMEN_TEST_VOLUME;
test("motore reale: elenco capitoli e impaginazione di un capitolo", { skip: !volume }, async () => {
  const { chapters } = await listChapters(settings, volume!);
  assert.ok(chapters.length > 3 && chapters.every((c) => typeof c.id === "string"));
  const first = chapters.find((c) => c.file);
  assert.ok(first, "almeno un capitolo con file");
  const out = path.join(require("os").tmpdir(), "volumen-plugin-test");
  const res = await runEngine<BuildResult>(settings, buildArgs({ volume: volume!, format: "typst", chapters: [first!.id], out }));
  assert.equal(res.ok, true);
  assert.ok(res.pdf && res.pdf.endsWith(".pdf"));
});

test("errore del motore: volume inesistente -> EngineError con messaggio", async () => {
  await assert.rejects(runEngine(settings, buildArgs({ volume: "/non/esiste/volume.md", format: "typst" })),
    (e: any) => e.name === "Error" && /Nota del volume non trovata/.test(e.stderr));
});
