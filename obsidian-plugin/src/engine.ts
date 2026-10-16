// Chiamata al motore Python (`python -m volumen`): nessuna dipendenza da Obsidian, cosi' si prova da Node.
import { spawn } from "child_process";
import * as fs from "fs";
import * as os from "os";
import * as path from "path";

export interface EngineSettings {
  python: string;          // eseguibile Python con le dipendenze di requirements.txt ("" = rilevamento automatico)
  engineDir: string;       // cartella del progetto che contiene il pacchetto `volumen` ("" = automatica)
  extraPath: string;       // cartelle da aggiungere al PATH oltre a quelle note (typst, pandoc, gs)
}

/** Cartelle dove di solito stanno typst, pandoc e gs; si aggiungono al PATH se esistono. */
export const WELL_KNOWN_BIN_DIRS = [
  "/opt/homebrew/bin",      // Homebrew (Apple Silicon)
  "/usr/local/bin",         // Homebrew (Intel) e installazioni manuali
  "/opt/local/bin",         // MacPorts
  "/Library/TeX/texbin",    // MacTeX / BasicTeX
  "/usr/bin",
  "/bin",
];

export interface BuildOptions {
  volume: string;                  // percorso assoluto di volume.md
  format: "typst" | "docx";
  chapters?: string[];             // id dei capitoli (--chapter)
  annotations?: boolean;           // --annotations
  validate?: boolean;              // --validate: controlla senza impaginare
  typstSource?: boolean;           // --no-pdf --keep-typ: solo il sorgente .typ
  out?: string;                    // --out
  name?: string;                   // --name
}

export interface BuildResult {
  ok: boolean;
  volume: string;
  output_dir: string;
  written: string[];
  pdf: string | null;
  docx: string | null;
  typ?: string | null;
  validate?: boolean;
  anomalies: string;
  counts: Record<string, number>;
  n_included: number;
  n_excluded: number;
}

export interface ChapterRow {
  id: string;
  title: string;
  source: string;
  depth: number;
  file: string | null;
  dir: string | null;
}

export class EngineError extends Error {
  constructor(message: string, public stderr: string, public code: number | null) {
    super(message);
  }
}

export function buildArgs(o: BuildOptions): string[] {
  const a = ["-m", "volumen", "--json", "--volume", o.volume, "--format", o.format];
  if (o.chapters && o.chapters.length) a.push("--chapter", ...o.chapters);
  if (o.annotations) a.push("--annotations");
  if (o.validate) a.push("--validate");
  if (o.typstSource) a.push("--no-pdf", "--keep-typ");
  if (o.out) a.push("--out", o.out);
  if (o.name) a.push("--name", o.name);
  return a;
}

/** PATH del processo figlio: le cartelle indicate, quello ereditato, poi le cartelle note che esistono. */
export function childEnv(s: EngineSettings, base: NodeJS.ProcessEnv = process.env,
                         dirExists: (d: string) => boolean = fs.existsSync): NodeJS.ProcessEnv {
  const split = (v: string) => v.split(path.delimiter).map((x) => x.trim()).filter(Boolean);
  const parts = [...split(s.extraPath), ...split(base.PATH || ""), ...WELL_KNOWN_BIN_DIRS.filter((d) => dirExists(d))];
  return { ...base, PATH: [...new Set(parts)].join(path.delimiter), PYTHONIOENCODING: "utf-8", PYTHONUTF8: "1" };
}

/** Primo eseguibile `name` nelle cartelle del PATH, o null. */
export function findBinary(name: string, env: NodeJS.ProcessEnv): string | null {
  for (const dir of (env.PATH || "").split(path.delimiter).filter(Boolean)) {
    const f = path.join(dir, name);
    try {
      fs.accessSync(f, fs.constants.X_OK);
      if (fs.statSync(f).isFile()) return f;
    } catch { /* non c'e' */ }
  }
  return null;
}

/** La cartella del progetto a partire dalla cartella del plugin (se e' un link al repo: il genitore). */
export function detectEngineDir(pluginDir: string): string | null {
  try {
    const candidate = path.resolve(fs.realpathSync(pluginDir), "..");
    return fs.existsSync(path.join(candidate, "volumen", "__init__.py")) ? candidate : null;
  } catch {
    return null;
  }
}

/** Interpreti Python da provare, nell'ordine: quello indicato, python3 nel PATH, pyenv, Homebrew, sistema. */
export function pythonCandidates(configured: string, home: string = os.homedir()): string[] {
  const out: string[] = [];
  if (configured) out.push(configured);
  out.push("python3");
  out.push(path.join(home, ".pyenv", "shims", "python3"));
  try {
    const dir = path.join(home, ".pyenv", "versions");
    for (const v of fs.readdirSync(dir).sort().reverse()) out.push(path.join(dir, v, "bin", "python3"));
  } catch { /* nessun pyenv */ }
  out.push("/opt/homebrew/bin/python3", "/usr/local/bin/python3", "/usr/bin/python3");
  return [...new Set(out)];
}

const REQUIRED_MODULES = "import docx, yaml, fitz, PIL";

function tryPython(python: string, env: NodeJS.ProcessEnv): Promise<string | null> {
  return new Promise((resolve) => {
    const child = spawn(python, ["-c", REQUIRED_MODULES], { env });
    let err = "";
    const timer = setTimeout(() => { child.kill(); resolve("nessuna risposta in 15 s"); }, 15000);
    child.stderr.on("data", (d) => (err += d.toString("utf8")));
    child.on("error", (e) => { clearTimeout(timer); resolve(e.message); });
    child.on("close", (code) => {
      clearTimeout(timer);
      resolve(code === 0 ? null : (err.trim().split("\n").slice(-1)[0] || `codice ${code}`));
    });
  });
}

export interface EnvReport {
  python: string | null;
  engineDir: string | null;
  typst: string | null;
  pandoc: string | null;
  gs: string | null;
  problems: string[];
  ok: boolean;
}

/** Controlla l'ambiente: cartella del motore, Python con le dipendenze, typst, pandoc (gs e' facoltativo). */
export async function probeEnvironment(s: EngineSettings, pluginDir: string | null): Promise<EnvReport> {
  const env = childEnv(s);
  const problems: string[] = [];
  const engineDir = s.engineDir || (pluginDir ? detectEngineDir(pluginDir) : null);
  if (!engineDir || !fs.existsSync(path.join(engineDir, "volumen", "__init__.py"))) {
    problems.push("Cartella del motore non trovata: indicala nelle impostazioni (quella che contiene la cartella `volumen`).");
  }
  let python: string | null = null;
  const errors: string[] = [];
  for (const cand of pythonCandidates(s.python)) {
    const err = await tryPython(cand, env);
    if (err === null) { python = cand; break; }
    errors.push(`${cand}: ${err}`);
    if (s.python && cand === s.python) break;          // un Python indicato a mano non si sostituisce di nascosto
  }
  if (!python) problems.push(`Python con le dipendenze non trovato (pip install -r requirements.txt). ${errors[0] || ""}`.trim());
  const typst = findBinary("typst", env);
  const pandoc = findBinary("pandoc", env);
  if (!typst) problems.push("`typst` non trovato (brew install typst).");
  if (!pandoc) problems.push("`pandoc` non trovato (brew install pandoc).");
  return { python, engineDir, typst, pandoc, gs: findBinary("gs", env), problems, ok: problems.length === 0 };
}

/** Esegue il motore; stdout e' solo l'oggetto JSON, il resto (progresso, errori) e' su stderr. */
export function runEngine<T>(s: EngineSettings, args: string[], onLog?: (line: string) => void): Promise<T> {
  return new Promise((resolve, reject) => {
    const child = spawn(s.python, args, { cwd: s.engineDir, env: childEnv(s) });
    let out = "";
    let err = "";
    child.stdout.on("data", (d) => (out += d.toString("utf8")));
    child.stderr.on("data", (d) => {
      const text = d.toString("utf8");
      err += text;
      if (onLog) text.split("\n").filter(Boolean).forEach(onLog);
    });
    child.on("error", (e) =>
      reject(new EngineError(`Impossibile avviare ${s.python}: ${e.message}`, err, null)));
    child.on("close", (code) => {
      if (code !== 0) {
        const last = err.trim().split("\n").filter(Boolean).slice(-1)[0] || `codice di uscita ${code}`;
        return reject(new EngineError(last, err, code));
      }
      try {
        resolve(JSON.parse(out.trim().split("\n").slice(-1)[0]) as T);
      } catch {
        reject(new EngineError("Risposta del motore non valida (JSON atteso)", out + "\n" + err, code));
      }
    });
  });
}

export function listChapters(s: EngineSettings, volume: string): Promise<{ volume: string; chapters: ChapterRow[] }> {
  return runEngine(s, ["-m", "volumen", "--json", "--volume", volume, "--list-chapters"]);
}

/** Capitolo a cui appartiene un file: il capitolo Markdown con quel file, o la cartella `source=<dir>` che lo contiene. */
export function chapterForFile(rows: ChapterRow[], absFile: string, volumeDir: string): ChapterRow | undefined {
  const target = path.resolve(absFile);
  const direct = rows.find((r) => r.file && path.resolve(r.file) === target);
  if (direct) return direct;
  return rows.find((r) => {
    if (!r.dir) return false;
    const d = path.resolve(volumeDir, r.dir) + path.sep;
    return target.startsWith(d);
  });
}
