import { App, FileSystemAdapter, Modal, Notice, Plugin, PluginSettingTab, Setting, TFile } from "obsidian";
import * as path from "path";
import {
  BuildOptions, BuildResult, EngineError, EngineSettings, EnvReport, buildArgs, chapterForFile, listChapters,
  probeEnvironment, runEngine,
} from "./engine";

interface PluginSettings extends EngineSettings {
  volumeNote: string;        // percorso della nota del volume, relativo al vault (vuoto = automatico)
  openAfter: boolean;        // apre il PDF/DOCX a fine lavoro
}

const DEFAULTS: PluginSettings = {
  python: "",           // vuoto = rilevamento automatico
  engineDir: "",        // vuoto = automatica (il repo che contiene questo plugin)
  extraPath: "",        // oltre alle cartelle note (Homebrew, MacPorts, MacTeX)
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

    this.addRibbonIcon("book-open", "Impagina il volume (PDF)", () => this.build({ format: "typst" }));

    this.addCommand({ id: "build-pdf", name: "Impagina il volume (PDF)", callback: () => this.build({ format: "typst" }) });
    this.addCommand({ id: "build-pdf-annotations", name: "Impagina il volume (PDF con annotazioni)",
      callback: () => this.build({ format: "typst", annotations: true }) });
    this.addCommand({ id: "build-docx", name: "Impagina il volume (DOCX)", callback: () => this.build({ format: "docx" }) });
    this.addCommand({ id: "build-chapter", name: "Impagina il capitolo della nota corrente (PDF)",
      callback: () => this.buildCurrentChapter() });
    this.addCommand({ id: "build-chapter-annotations", name: "Impagina il capitolo della nota corrente (PDF con annotazioni)",
      callback: () => this.buildCurrentChapter(true) });
    this.addCommand({ id: "validate", name: "Controlla il volume (senza impaginare)", callback: () => this.validate() });
    this.addCommand({ id: "typst-source", name: "Mostra il sorgente Typst del volume", callback: () => this.showTypst() });
    this.addCommand({ id: "check-env", name: "Verifica l'ambiente (Python, Typst, Pandoc)", callback: () => this.checkEnvironment(true) });
    this.addCommand({ id: "open-anomalies", name: "Apri le anomalie dell'ultima impaginazione",
      callback: () => this.openAnomalies() });
    this.addCommand({ id: "open-volume", name: "Apri la nota del volume", callback: () => this.openVolumeNote() });

    this.addSettingTab(new VolumenSettingTab(this.app, this));
  }

  async loadSettings() { this.settings = Object.assign({}, DEFAULTS, await this.loadData()); }
  async saveSettings() { await this.saveData(this.settings); }
  resetEnvironment() { this.env = null; }

  private setStatus(text: string) { this.status.setText(text ? `Volumen: ${text}` : ""); }

  private vaultBase(): string {
    const adapter = this.app.vault.adapter;
    if (!(adapter instanceof FileSystemAdapter)) throw new Error("Serve un vault su disco (non supportato su mobile).");
    return adapter.getBasePath();
  }

  /** La nota del volume: l'impostazione, altrimenti la nota attiva se `type: volume`, altrimenti l'unica del vault. */
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

  /** Cartella di questo plugin su disco (il link simbolico viene risolto da `detectEngineDir`). */
  private pluginDirAbs(): string | null {
    try { return this.manifest.dir ? path.join(this.vaultBase(), this.manifest.dir) : null; } catch { return null; }
  }

  /** Impostazioni con motore e Python risolti: automatici se lasciati vuoti, controllati una volta per sessione. */
  private env: EnvReport | null = null;

  private async resolveEngine(): Promise<EngineSettings | null> {
    if (!this.env || !this.env.ok) this.env = await probeEnvironment(this.settings, this.pluginDirAbs());
    if (!this.env.ok || !this.env.python || !this.env.engineDir) {
      new Notice(`Volumen: ${this.env.problems[0] || "ambiente incompleto"} (comando «Verifica l'ambiente»).`, 9000);
      return null;
    }
    return { python: this.env.python, engineDir: this.env.engineDir, extraPath: this.settings.extraPath };
  }

  private async checkEnvironment(show: boolean) {
    this.env = await probeEnvironment(this.settings, this.pluginDirAbs());
    const e = this.env;
    const mark = (v: string | null, optional = false) => (v ? `✔ ${v}` : optional ? "– (facoltativo)" : "✘ non trovato");
    const lines = [
      `Motore (cartella):  ${e.engineDir ? "✔ " + e.engineDir : "✘ non trovata"}`,
      `Python:             ${mark(e.python)}`,
      `Typst:              ${mark(e.typst)}`,
      `Pandoc:             ${mark(e.pandoc)}`,
      `Ghostscript (gs):   ${mark(e.gs, true)}`,
      "",
      ...(e.problems.length ? ["Da sistemare:", ...e.problems.map((p) => "• " + p)] : ["Tutto a posto."]),
    ];
    if (show) new LogModal(this.app, "Volumen: ambiente", lines.join("\n")).open();
    return e;
  }

  private requireVolume(): { volumeAbs: string; volumeFile: TFile } | null {
    const volumeFile = this.findVolumeNote();
    if (!volumeFile) {
      new Notice("Volumen: nessuna nota del volume. Aggiungi `type: volume` al frontmatter di volume.md o indicala nelle impostazioni.");
      return null;
    }
    return { volumeAbs: path.join(this.vaultBase(), volumeFile.path), volumeFile };
  }

  /** Lancia il motore (una sola esecuzione alla volta) e restituisce l'esito, o null in caso di errore (gia' mostrato). */
  private async run(o: Omit<BuildOptions, "volume">, label: string): Promise<BuildResult | null> {
    const setup = this.requireVolume();
    if (!setup) return null;
    if (this.busy) { new Notice("Volumen: operazione già in corso."); return null; }
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
      this.setStatus(n ? `${n} anomalie` : "ok");
      return res;
    } catch (e) {
      this.setStatus("errore");
      const err = e as EngineError;
      new Notice(`Volumen: errore — ${err.message}`, 8000);
      new LogModal(this.app, "Volumen: errore", err.stderr || err.message).open();
      return null;
    } finally {
      this.busy = false;
    }
  }

  private summary(res: BuildResult): string {
    const n = Object.values(res.counts).reduce((a, b) => a + b, 0);
    return n ? `${n} anomalie (clic sulla barra di stato per vederle).` : "nessuna anomalia.";
  }

  private async build(o: Omit<BuildOptions, "volume">) {
    const label = `${o.chapters?.length ? "capitolo " + o.chapters.join(", ") : "volume"} (${o.format === "docx" ? "DOCX" : "PDF"})`;
    const res = await this.run(o, `impagino ${label}`);
    if (!res) return;
    new Notice(`Volumen: fatto, ${this.summary(res)}`);
    const target = res.pdf || res.docx;
    if (this.settings.openAfter && target) this.openExternal(target);
  }

  private async validate() {
    const res = await this.run({ format: "typst", validate: true }, "controllo il volume");
    if (!res) return;
    new Notice(`Volumen: ${res.n_included} voci controllate, ${this.summary(res)}`, 7000);
    await this.openAnomalies();
  }

  private async showTypst() {
    const res = await this.run({ format: "typst", typstSource: true }, "genero il sorgente Typst");
    if (!res) return;
    if (res.typ) this.openExternal(res.typ);
    else new Notice("Volumen: sorgente Typst non prodotto.");
  }

  private async buildCurrentChapter(annotations = false) {
    const setup = this.requireVolume();
    const active = this.app.workspace.getActiveFile();
    if (!setup) return;
    if (!active) { new Notice("Volumen: nessuna nota aperta."); return; }
    const engine = await this.resolveEngine();
    if (!engine) return;
    try {
      const { chapters } = await listChapters(engine, setup.volumeAbs);
      const row = chapterForFile(chapters, path.join(this.vaultBase(), active.path), path.dirname(setup.volumeAbs));
      if (!row) { new Notice(`Volumen: «${active.basename}» non è un capitolo del volume.`); return; }
      await this.build({ format: "typst", chapters: [row.id], annotations });
    } catch (e) {
      const err = e as EngineError;
      new LogModal(this.app, "Volumen: errore", err.stderr || err.message).open();
    }
  }

  private openExternal(file: string) {
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    const { shell } = require("electron");
    shell.openPath(file);
  }

  private async openAnomalies() {
    if (!this.last) { new Notice("Volumen: nessuna impaginazione eseguita in questa sessione."); return; }
    const rel = path.relative(this.vaultBase(), this.last.anomalies);
    const file = rel.startsWith("..") ? null : this.app.vault.getAbstractFileByPath(rel.split(path.sep).join("/"));
    if (file instanceof TFile) { await this.app.workspace.getLeaf(true).openFile(file); return; }
    this.openExternal(this.last.anomalies);      // cartella di output fuori dal vault
  }

  private async openVolumeNote() {
    const f = this.findVolumeNote();
    if (f) await this.app.workspace.getLeaf(true).openFile(f);
    else new Notice("Volumen: nessuna nota del volume.");
  }
}

class VolumenSettingTab extends PluginSettingTab {
  constructor(app: App, private plugin: VolumenPlugin) { super(app, plugin); }

  display(): void {
    const { containerEl } = this;
    containerEl.empty();
    const s = this.plugin.settings;
    containerEl.createEl("p", { text: "Di norma non serve impostare nulla: il plugin trova da solo il motore, Python, Typst e Pandoc. " +
      "Usa il comando «Verifica l'ambiente» per vedere cosa ha trovato." });
    const text = (name: string, desc: string, key: "python" | "engineDir" | "extraPath" | "volumeNote", placeholder = "") =>
      new Setting(containerEl).setName(name).setDesc(desc).addText((t) =>
        t.setPlaceholder(placeholder).setValue(s[key]).onChange(async (v) => {
          s[key] = v.trim();
          this.plugin.resetEnvironment();
          await this.plugin.saveSettings();
        }));

    text("Nota del volume", "Percorso nel vault (es. md/volume.md). Vuoto = la nota attiva o l'unica con `type: volume`.", "volumeNote", "automatico");
    new Setting(containerEl).setName("Apri il file a fine lavoro").addToggle((t) =>
      t.setValue(s.openAfter).onChange(async (v) => { s.openAfter = v; await this.plugin.saveSettings(); }));
    containerEl.createEl("h3", { text: "Avanzate (solo se il rilevamento automatico non basta)" });
    text("Cartella del motore", "La cartella con il pacchetto `volumen`. Vuoto = quella che contiene questo plugin.", "engineDir", "automatica");
    text("Python", "Eseguibile con le dipendenze di requirements.txt. Vuoto = ricerca automatica (PATH, pyenv, Homebrew).", "python", "automatico");
    text("PATH aggiuntivo", "Altre cartelle con typst, pandoc, gs, separate da «:». Si sommano a Homebrew, MacPorts e MacTeX.", "extraPath", "");
  }
}
