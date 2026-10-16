// Calls the Python engine (`python -m volumen`): no dependency on Obsidian, so it can be tested from Node.
import { spawn } from "child_process";
import * as fs from "fs";
import * as os from "os";
import * as path from "path";

export interface EngineSettings {
  python: string;          // Python executable with the dependencies of requirements.txt ("" = automatic detection)
  engineDir: string;       // project folder containing the `volumen` package ("" = automatic)
  extraPath: string;       // folders to add to the PATH besides the well-known ones (typst, pandoc, gs)
}

/** Folders where typst, pandoc and gs usually live; added to the PATH if they exist. */
export const WELL_KNOWN_BIN_DIRS = [
  "/opt/homebrew/bin",      // Homebrew (Apple Silicon)
  "/usr/local/bin",         // Homebrew (Intel) and manual installs
  "/opt/local/bin",         // MacPorts
  "/Library/TeX/texbin",    // MacTeX / BasicTeX
  "/usr/bin",
  "/bin",
];

export interface BuildOptions {
  volume: string;                  // absolute path of volume.md
  format: "typst" | "docx";
  chapters?: string[];             // chapter ids (--chapter)
  annotations?: boolean;           // --annotations
  validate?: boolean;              // --validate: check without typesetting
  typstSource?: boolean;           // --no-pdf --keep-typ: only the .typ source
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

/** PATH of the child process: the given folders, the inherited one, then the well-known folders that exist. */
export function childEnv(s: EngineSettings, base: NodeJS.ProcessEnv = process.env,
                         dirExists: (d: string) => boolean = fs.existsSync): NodeJS.ProcessEnv {
  const split = (v: string) => v.split(path.delimiter).map((x) => x.trim()).filter(Boolean);
  const parts = [...split(s.extraPath), ...split(base.PATH || ""), ...WELL_KNOWN_BIN_DIRS.filter((d) => dirExists(d))];
  return { ...base, PATH: [...new Set(parts)].join(path.delimiter), PYTHONIOENCODING: "utf-8", PYTHONUTF8: "1" };
}

/** First executable `name` in the PATH folders, or null. */
export function findBinary(name: string, env: NodeJS.ProcessEnv): string | null {
  for (const dir of (env.PATH || "").split(path.delimiter).filter(Boolean)) {
    const f = path.join(dir, name);
    try {
      fs.accessSync(f, fs.constants.X_OK);
      if (fs.statSync(f).isFile()) return f;
    } catch { /* not there */ }
  }
  return null;
}

/** The project folder, starting from the plugin folder (if it is a link to the repo: its parent). */
export function detectEngineDir(pluginDir: string): string | null {
  try {
    const candidate = path.resolve(fs.realpathSync(pluginDir), "..");
    return fs.existsSync(path.join(candidate, "volumen", "__init__.py")) ? candidate : null;
  } catch {
    return null;
  }
}

/** Python interpreters to try, in order: the configured one, python3 on the PATH, pyenv, Homebrew, system. */
export function pythonCandidates(configured: string, home: string = os.homedir()): string[] {
  const out: string[] = [];
  if (configured) out.push(configured);
  out.push("python3");
  out.push(path.join(home, ".pyenv", "shims", "python3"));
  try {
    const dir = path.join(home, ".pyenv", "versions");
    for (const v of fs.readdirSync(dir).sort().reverse()) out.push(path.join(dir, v, "bin", "python3"));
  } catch { /* no pyenv */ }
  out.push("/opt/homebrew/bin/python3", "/usr/local/bin/python3", "/usr/bin/python3");
  return [...new Set(out)];
}

const REQUIRED_MODULES = "import docx, yaml, fitz, PIL";

function tryPython(python: string, env: NodeJS.ProcessEnv): Promise<string | null> {
  return new Promise((resolve) => {
    const child = spawn(python, ["-c", REQUIRED_MODULES], { env });
    let err = "";
    const timer = setTimeout(() => { child.kill(); resolve("no answer within 15 s"); }, 15000);
    child.stderr.on("data", (d) => (err += d.toString("utf8")));
    child.on("error", (e) => { clearTimeout(timer); resolve(e.message); });
    child.on("close", (code) => {
      clearTimeout(timer);
      resolve(code === 0 ? null : (err.trim().split("\n").slice(-1)[0] || `exit code ${code}`));
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

/** Checks the environment: engine folder, Python with the dependencies, typst, pandoc (gs is optional). */
export async function probeEnvironment(s: EngineSettings, pluginDir: string | null): Promise<EnvReport> {
  const env = childEnv(s);
  const problems: string[] = [];
  const engineDir = s.engineDir || (pluginDir ? detectEngineDir(pluginDir) : null);
  if (!engineDir || !fs.existsSync(path.join(engineDir, "volumen", "__init__.py"))) {
    problems.push("Engine folder not found: set it in the settings (the one containing the `volumen` folder).");
  }
  let python: string | null = null;
  const errors: string[] = [];
  for (const cand of pythonCandidates(s.python)) {
    const err = await tryPython(cand, env);
    if (err === null) { python = cand; break; }
    errors.push(`${cand}: ${err}`);
    if (s.python && cand === s.python) break;          // a manually configured Python is never silently replaced
  }
  if (!python) problems.push(`Python with the dependencies not found (pip install -r requirements.txt). ${errors[0] || ""}`.trim());
  const typst = findBinary("typst", env);
  const pandoc = findBinary("pandoc", env);
  if (!typst) problems.push("`typst` not found (brew install typst).");
  if (!pandoc) problems.push("`pandoc` not found (brew install pandoc).");
  return { python, engineDir, typst, pandoc, gs: findBinary("gs", env), problems, ok: problems.length === 0 };
}

/** Runs the engine; stdout is only the JSON object, everything else (progress, errors) goes to stderr. */
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
      reject(new EngineError(`Cannot start ${s.python}: ${e.message}`, err, null)));
    child.on("close", (code) => {
      if (code !== 0) {
        const last = err.trim().split("\n").filter(Boolean).slice(-1)[0] || `exit code ${code}`;
        return reject(new EngineError(last, err, code));
      }
      try {
        resolve(JSON.parse(out.trim().split("\n").slice(-1)[0]) as T);
      } catch {
        reject(new EngineError("Invalid engine response (JSON expected)", out + "\n" + err, code));
      }
    });
  });
}

export function listChapters(s: EngineSettings, volume: string): Promise<{ volume: string; chapters: ChapterRow[] }> {
  return runEngine(s, ["-m", "volumen", "--json", "--volume", volume, "--list-chapters"]);
}

/** The chapter a file belongs to: the Markdown chapter with that file, or the `source=<dir>` folder that contains it. */
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
