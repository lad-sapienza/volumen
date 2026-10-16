# Volumen by LAD: plugin Obsidian

Impagina il volume dal vault: i comandi lanciano il motore Python (`python3 -m volumen --json`) sulla nota `volume.md`
(`type: volume` nel frontmatter). Solo desktop. Il plugin non contiene logica di impaginazione: legge l'esito JSON del motore.

## Comandi

| Comando | Cosa fa |
|---|---|
| Impagina il volume (PDF) | PDF con Typst; lo apre a fine lavoro (impostazione) |
| Impagina il volume (PDF con annotazioni) | come sopra, con le annotazioni CriticMarkup come commenti PDF |
| Impagina il volume (DOCX) | DOCX |
| Impagina il capitolo della nota corrente (PDF) | solo il capitolo della nota aperta (o la cartella `source=…` che la contiene) |
| Impagina il capitolo della nota corrente (PDF con annotazioni) | come sopra, con le annotazioni CriticMarkup come commenti PDF |
| Controlla il volume (senza impaginare) | verifica file e link mancanti, immagini, citazioni e apre `anomalie.md`, senza produrre PDF (rapido, prima di una consegna) |
| Mostra il sorgente Typst del volume | genera il `.typ` e lo apre (per vedere cosa riceve Typst) |
| Verifica l'ambiente (Python, Typst, Pandoc) | mostra cosa ha trovato il plugin e cosa manca, con il comando per installarlo |
| Apri le anomalie dell'ultima impaginazione | apre `anomalie.md` (se la cartella di output è nel vault; clic anche sulla barra di stato) |
| Apri la nota del volume | |

Un'icona nella barra laterale lancia «Impagina il volume (PDF)». La barra di stato mostra l'avanzamento e il numero di anomalie.

## Installazione (sviluppo)

```bash
cd obsidian-plugin
npm install
npm run build            # genera main.js
mkdir -p "<vault>/.obsidian/plugins/volumen"
cp main.js manifest.json "<vault>/.obsidian/plugins/volumen/"      # oppure un link simbolico
```

Poi in Obsidian: Impostazioni → Plugin della community → attiva «Volumen by LAD».

## Impostazioni

Di norma **non serve impostare nulla**: il plugin trova da solo
- la **cartella del motore** (il repo che contiene questo plugin, anche tramite link simbolico);
- **Python**: prova `python3` nel PATH, gli shim e le versioni di pyenv, Homebrew e il sistema, e sceglie il primo che ha le
  dipendenze di `requirements.txt` (`python-docx`, `pyyaml`, `pymupdf`, `pillow`);
- **typst, pandoc, gs**: li cerca nel PATH più Homebrew (`/opt/homebrew/bin`, `/usr/local/bin`), MacPorts e MacTeX
  (Obsidian non eredita il PATH del terminale).

Il comando «Verifica l'ambiente» mostra cosa ha trovato. Le impostazioni servono solo se il rilevamento non basta:

- **Nota del volume**: percorso nel vault (es. `md/volume.md`). Vuoto = la nota attiva se ha `type: volume`, altrimenti l'unica del vault.
- **Apri il file a fine lavoro**.
- Avanzate: **Cartella del motore**, **Python** (un percorso indicato a mano non viene mai sostituito di nascosto), **PATH aggiuntivo**.

## Prove

```bash
npm test                                           # test unitari (ambiente, argomenti, link simbolici)
VOLUMEN_PYTHON=/percorso/python3 VOLUMEN_TEST_VOLUME=/percorso/volume.md npm test   # + prova con il motore reale
```
