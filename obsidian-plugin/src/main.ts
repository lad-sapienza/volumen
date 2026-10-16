import { App, FileSystemAdapter, Modal, Notice, Plugin, PluginSettingTab, Setting, TFile } from "obsidian";
import * as path from "path";
import {
  BuildOptions, BuildResult, EngineError, EngineSettings, EnvReport, buildArgs, chapterForFile, listChapters,
  probeEnvironment, runEngine,
} from "./engine";

interface PluginSettings extends EngineSettings {
  volumeNote: string;        // path of the volume note, relative to the vault (empty = automatic)
  openAfter: boolean;        // open the PDF/DOCX when finished
}

const DEFAULTS: PluginSettings = {
  python: "",           // empty = automatic detection
  engineDir: "",        // empty = automatic (the repository that contains this plugin)
  extraPath: "",        // in addition to the well-known folders (Homebrew, MacPorts, MacTeX)
  volumeNote: "",
  openAfter: true,
};

class LogModal extends Modal {
  constructor(app: App, private title: string, private body: string) { super(app); }
  onOpen() {
    this.titleEl.setText(this.title);
    const pre = this.contentEl.createEl("pre");
    pre.setText(this.body);
    pre.style.whiteSpace = "pre-wrap";
    pre.style.userSelect = "text";
    pre.style.maxHeight = "60vh";
    pre.style.overflow = "auto";
  }
  onClose() { this.contentEl.empty(); }
}

export default class VolumenPlugin extends Plugin {
  settings: PluginSettings = { ...DEFAULTS };
  private status!: HTMLElement;
  private busy = false;
  private last: BuildResult | null = null;

  async onload() {
    await this.loadSettings();
    this.status = this.addStatusBarItem();
    this.status.addClass("mod-clickable");
    this.status.onClickEvent(() => this.openAnomalies());
    this.setStatus("");

    this.addRibbonIcon("book-open", "Typeset volume (PDF)", () => this.build({ format: "typst" }));

    this.addCommand({ id: "build-pdf", name: "Typeset volume (PDF)", callback: () => this.build({ format: "typst" }) });
    this.addCommand({ id: "build-pdf-annotations", name: "Typeset volume (PDF with annotations)",
      callback: () => this.build({ format: "typst", annotations: true }) });
    this.addCommand({ id: "build-docx", name: "Typeset volume (DOCX)", callback: () => this.build({ format: "docx" }) });
    this.addCommand({ id: "build-chapter", name: "Typeset current chapter (PDF)",
      callback: () => this.buildCurrentChapter() });
    this.addCommand({ id: "build-chapter-annotations", name: "Typeset current chapter (PDF with annotations)",
      callback: () => this.buildCurrentChapter(true) });
    this.addCommand({ id: "validate", name: "Check volume (without typesetting)", callback: () => this.validate() });
    this.addCommand({ id: "typst-source", name: "Show Typst source of the volume", callback: () => this.showTypst() });
    this.addCommand({ id: "check-env", name: "Check environment (Python, Typst, Pandoc)", callback: () => this.checkEnvironment(true) });
    this.addCommand({ id: "open-anomalies", name: "Open anomalies of the last run",
      callback: () => this.openAnomalies() });
    this.addCommand({ id: "open-volume", name: "Open volume note", callback: () => this.openVolumeNote() });

    this.addSettingTab(new VolumenSettingTab(this.app, this));
  }

  async loadSettings() { this.settings = Object.assign({}, DEFAULTS, await this.loadData()); }
  async saveSettings() { await this.saveData(this.settings); }
  resetEnvironment() { this.env = null; }

  private setStatus(text: string) { this.status.setText(text ? `Volumen: ${text}` : ""); }

  private vaultBase(): string {
    const adapter = this.app.vault.adapter;
    if (!(adapter instanceof FileSystemAdapter)) throw new Error("A vault on disk is required (not supported on mobile).");
    return adapter.getBasePath();
  }

  /** The volume note: the setting, otherwise the active note if `type: volume`, otherwise the only one in the vault. */
  private findVolumeNote(): TFile | null {
    if (this.settings.volumeNote) {
      const f = this.app.vault.getAbstractFileByPath(this.settings.volumeNote);
      return f instanceof TFile ? f : null;
    }
    const isVolume = (f: TFile) => this.app.metadataCache.getFileCache(f)?.frontmatter?.type === "volume";
    const active = this.app.workspace.getActiveFile();
    if (active && isVolume(active)) return active;
    const all = this.app.vault.getMarkdownFiles().filter(isVolume);
    return all.length === 1 ? all[0] : null;
  }

  /** This plugin's folder on disk (the symlink is resolved by `detectEngineDir`). */
  private pluginDirAbs(): string | null {
    try { return this.manifest.dir ? path.join(this.vaultBase(), this.manifest.dir) : null; } catch { return null; }
  }

  /** Settings with engine and Python resolved: automatic when left empty, checked once per session. */
  private env: EnvReport | null = null;

  private async resolveEngine(): Promise<EngineSettings | null> {
    if (!this.env || !this.env.ok) this.env = await probeEnvironment(this.settings, this.pluginDirAbs());
    if (!this.env.ok || !this.env.python || !this.env.engineDir) {
      new Notice(`Volumen: ${this.env.problems[0] || "incomplete environment"} (command \"Check environment\").`, 9000);
      return null;
    }
    return { python: this.env.python, engineDir: this.env.engineDir, extraPath: this.settings.extraPath };
  }

  private async checkEnvironment(show: boolean) {
    this.env = await probeEnvironment(this.settings, this.pluginDirAbs());
    const e = this.env;
    const mark = (v: string | null, optional = false) => (v ? `✔ ${v}` : optional ? "– (optional)" : "✘ not found");
    const lines = [
      `Engine (folder):    ${e.engineDir ? "✔ " + e.engineDir : "✘ not found"}`,
      `Python:             ${mark(e.python)}`,
      `Typst:              ${mark(e.typst)}`,
      `Pandoc:             ${mark(e.pandoc)}`,
      `Ghostscript (gs):   ${mark(e.gs, true)}`,
      "",
      ...(e.problems.length ? ["To fix:", ...e.problems.map((p) => "• " + p)] : ["All good."]),
    ];
    if (show) new LogModal(this.app, "Volumen: environment", lines.join("\n")).open();
    return e;
  }

  private requireVolume(): { volumeAbs: string; volumeFile: TFile } | null {
    const volumeFile = this.findVolumeNote();
    if (!volumeFile) {
      new Notice("Volumen: no volume note found. Add `type: volume` to the frontmatter of volume.md or set it in the settings.");
      return null;
    }
    return { volumeAbs: path.join(this.vaultBase(), volumeFile.path), volumeFile };
  }

  /** Runs the engine (one run at a time) and returns the result, or null on error (already shown). */
  private async run(o: Omit<BuildOptions, "volume">, label: string): Promise<BuildResult | null> {
    const setup = this.requireVolume();
    if (!setup) return null;
    if (this.busy) { new Notice("Volumen: an operation is already running."); return null; }
    this.busy = true;
    try {
      const engine = await this.resolveEngine();
      if (!engine) return null;
      this.setStatus(`${label}…`);
      new Notice(`Volumen: ${label}…`);
      const res = await runEngine<BuildResult>(engine, buildArgs({ ...o, volume: setup.volumeAbs }),
        (l) => this.setStatus(l.slice(0, 60)));
      this.last = res;
      const n = Object.values(res.counts).reduce((a, b) => a + b, 0);
      this.setStatus(n ? `${n} anomalies` : "ok");
      return res;
    } catch (e) {
      this.setStatus("error");
      const err = e as EngineError;
      new Notice(`Volumen: error — ${err.message}`, 8000);
      new LogModal(this.app, "Volumen: error", err.stderr || err.message).open();
      return null;
    } finally {
      this.busy = false;
    }
  }

  private summary(res: BuildResult): string {
    const n = Object.values(res.counts).reduce((a, b) => a + b, 0);
    return n ? `${n} anomalies (click the status bar to see them).` : "no anomalies.";
  }

  private async build(o: Omit<BuildOptions, "volume">) {
    const label = `${o.chapters?.length ? "chapter " + o.chapters.join(", ") : "volume"} (${o.format === "docx" ? "DOCX" : "PDF"})`;
    const res = await this.run(o, `typesetting ${label}`);
    if (!res) return;
    new Notice(`Volumen: done, ${this.summary(res)}`);
    const target = res.pdf || res.docx;
    if (this.settings.openAfter && target) this.openExternal(target);
  }

  private async validate() {
    const res = await this.run({ format: "typst", validate: true }, "checking the volume");
    if (!res) return;
    new Notice(`Volumen: ${res.n_included} entries checked, ${this.summary(res)}`, 7000);
    await this.openAnomalies();
  }

  private async showTypst() {
    const res = await this.run({ format: "typst", typstSource: true }, "generating the Typst source");
    if (!res) return;
    if (res.typ) this.openExternal(res.typ);
    else new Notice("Volumen: no Typst source was produced.");
  }

  private async buildCurrentChapter(annotations = false) {
    const setup = this.requireVolume();
    const active = this.app.workspace.getActiveFile();
    if (!setup) return;
    if (!active) { new Notice("Volumen: no note is open."); return; }
    const engine = await this.resolveEngine();
    if (!engine) return;
    try {
      const { chapters } = await listChapters(engine, setup.volumeAbs);
      const row = chapterForFile(chapters, path.join(this.vaultBase(), active.path), path.dirname(setup.volumeAbs));
      if (!row) { new Notice(`Volumen: \"${active.basename}\" is not a chapter of the volume.`); return; }
      await this.build({ format: "typst", chapters: [row.id], annotations });
    } catch (e) {
      const err = e as EngineError;
      new LogModal(this.app, "Volumen: error", err.stderr || err.message).open();
    }
  }

  private openExternal(file: string) {
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    const { shell } = require("electron");
    shell.openPath(file);
  }

  private async openAnomalies() {
    if (!this.last) { new Notice("Volumen: nothing has been typeset in this session."); return; }
    const rel = path.relative(this.vaultBase(), this.last.anomalies);
    const file = rel.startsWith("..") ? null : this.app.vault.getAbstractFileByPath(rel.split(path.sep).join("/"));
    if (file instanceof TFile) { await this.app.workspace.getLeaf(true).openFile(file); return; }
    this.openExternal(this.last.anomalies);      // output folder outside the vault
  }

  private async openVolumeNote() {
    const f = this.findVolumeNote();
    if (f) await this.app.workspace.getLeaf(true).openFile(f);
    else new Notice("Volumen: no volume note found.");
  }
}

class VolumenSettingTab extends PluginSettingTab {
  constructor(app: App, private plugin: VolumenPlugin) { super(app, plugin); }

  display(): void {
    const { containerEl } = this;
    containerEl.empty();
    const s = this.plugin.settings;
    containerEl.createEl("p", { text: "Normally nothing needs to be set: the plugin finds the engine, Python, Typst and Pandoc on its own. " +
      "Use the \"Check environment\" command to see what it found." });
    const text = (name: string, desc: string, key: "python" | "engineDir" | "extraPath" | "volumeNote", placeholder = "") =>
      new Setting(containerEl).setName(name).setDesc(desc).addText((t) =>
        t.setPlaceholder(placeholder).setValue(s[key]).onChange(async (v) => {
          s[key] = v.trim();
          this.plugin.resetEnvironment();
          await this.plugin.saveSettings();
        }));

    text("Volume note", "Path in the vault (e.g. md/volume.md). Empty = the active note or the only one with `type: volume`.", "volumeNote", "automatic");
    new Setting(containerEl).setName("Open the file when finished").addToggle((t) =>
      t.setValue(s.openAfter).onChange(async (v) => { s.openAfter = v; await this.plugin.saveSettings(); }));
    containerEl.createEl("h3", { text: "Advanced (only if automatic detection is not enough)" });
    text("Engine folder", "The folder containing the `volumen` package. Empty = the one that contains this plugin.", "engineDir", "automatic");
    text("Python", "Executable with the dependencies of requirements.txt. Empty = automatic search (PATH, pyenv, Homebrew).", "python", "automatic");
    text("Extra PATH", "More folders with typst, pandoc, gs, separated by \":\". Added to Homebrew, MacPorts and MacTeX.", "extraPath", "");
  }
}
