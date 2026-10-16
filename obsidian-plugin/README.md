# Volumen by LAD: Obsidian plugin

Typesets the volume from your vault: the commands run the Python engine (`python3 -m volumen --json`) on the `volume.md`
note (`type: volume` in the frontmatter). Desktop only. The plugin contains no typesetting logic: it just reads the JSON
result of the engine.

## Commands

| Command | What it does |
|---|---|
| Typeset volume (PDF) | PDF with Typst; opens it when finished (setting) |
| Typeset volume (PDF with annotations) | as above, with the CriticMarkup annotations as PDF comments |
| Typeset volume (DOCX) | DOCX |
| Typeset current chapter (PDF) | only the chapter of the open note (or the `source=…` folder that contains it) |
| Typeset current chapter (PDF with annotations) | as above, with the CriticMarkup annotations as PDF comments |
| Check volume (without typesetting) | checks missing files and links, images, citations and opens `anomalies.md`, without producing a PDF (quick, before a delivery) |
| Show Typst source of the volume | generates the `.typ` file and opens it (to see what Typst receives) |
| Check environment (Python, Typst, Pandoc) | shows what the plugin found and what is missing, with the command to install it |
| Open anomalies of the last run | opens `anomalies.md` (if the output folder is inside the vault; clicking the status bar does the same) |
| Open volume note | |

A ribbon icon runs "Typeset volume (PDF)". The status bar shows progress and the number of anomalies.

## Installation

**From a release (no Node needed).** Download `main.js` and `manifest.json` from the latest
[release](../../../releases) into `<vault>/.obsidian/plugins/volumen/`, then in Obsidian: Settings → Community plugins →
enable "Volumen by LAD". The plugin needs the engine: clone this repository, install its Python dependencies (see the main
README) and, if the plugin cannot find it by itself, set **Engine folder** in the plugin settings.

**For development.** Link this folder into the vault and build it:

```bash
cd obsidian-plugin
npm install
npm run build            # produces main.js
mkdir -p "<vault>/.obsidian/plugins"
ln -s "$PWD" "<vault>/.obsidian/plugins/volumen"      # or copy main.js and manifest.json
```

With the symlink the plugin finds the engine on its own: it is the parent folder of this one.

## Settings

Normally **nothing needs to be set**: the plugin finds on its own
- the **engine folder** (the repository that contains this plugin, also through a symlink);
- **Python**: it tries `python3` on the PATH, the pyenv shims and versions, Homebrew and the system, and picks the first one
  that has the dependencies of `requirements.txt` (`python-docx`, `pyyaml`, `pymupdf`, `pillow`);
- **typst, pandoc, gs**: it looks for them on the PATH plus Homebrew (`/opt/homebrew/bin`, `/usr/local/bin`), MacPorts and
  MacTeX (Obsidian does not inherit the terminal's PATH).

The "Check environment" command shows what it found. The settings are only needed if detection is not enough:

- **Volume note**: path in the vault (e.g. `md/volume.md`). Empty = the active note if it has `type: volume`, otherwise the only one in the vault.
- **Open the file when finished**.
- Advanced: **Engine folder**, **Python** (a manually given path is never silently replaced), **Extra PATH**.

## Tests

```bash
npm test                                           # unit tests (environment, arguments, symlinks)
VOLUMEN_PYTHON=/path/to/python3 VOLUMEN_TEST_VOLUME=/path/to/volume.md npm test   # + test with the real engine
```
