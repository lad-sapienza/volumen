# Volumen by LAD

Impaginazione di un volume da note Markdown (Obsidian/Zotero): capitoli, cartelle di schede, bibliografia → **PDF con
Typst** (formato di consegna) e **DOCX** (formato di lavoro). La composizione e lo stile stanno in una sola nota,
`volume.md`. Esiste un [plugin per Obsidian](obsidian-plugin/README.md) che lancia il motore dal vault.

Il motore fa solo layout: non corregge mai i dati o i testi, li segnala in `anomalie.md` / `.csv`.

Il motore legge solo file Markdown: nessuna rete, nessun database. Una cartella di file Markdown (`source=<cartella>`) può
essere composta come catalogo di schede.

Un volume completo da provare subito è in [`example/`](example/md/volume.md) (l'*Odissea* nella traduzione di Samuel Butler, 1900,
pubblico dominio): `python3 -m volumen --volume example/md/volume.md`.

## Struttura

Un solo file di composizione e stile:

| File | Contiene |
|---|---|
| `volume.md` | **tutto il volume**: titolo, autori, indice, capitoli (elenco di link ai file), percorsi, bibliografia e **stile** (blocchi `yaml`). Nota Obsidian **accanto ai Markdown dei contenuti**, non nel repo |

Codice: **motore** = `volumen/sources/*` (`markdown`; `folder` = una cartella di file Markdown, un file per voce) produce i
blocchi del modello (`volumen/model.py`); `volumen/render/typst.py` e `volumen/render/docx.py` li impaginano; `volumen/citations.py`
risolve le citazioni con pandoc. Il motore legge solo Markdown. Punto d'ingresso unico: `python3 -m volumen`.

### Classi di tabelle e figure (stile)

Il Markdown non porta mai misure: marca un blocco con una **classe** e lo stile (sezione «Stile» di `volume.md`) ne dice l'aspetto.

- Tabella: riga `{.nome}` subito dopo la tabella → `table.classes.<nome>`: `col_ratios` (pesi delle colonne),
  `markup` (`false`: le celle non interpretano `**`/`*`), `empty_cell`, `full_width` (Typst: mai fluttuante, a piena larghezza).
  Esempio del progetto: `{.finds}` (tabella dei reperti).
- Figura: attributo `{class=nome}` (o il nome storico `role=nome`) → `images.classes.<nome>`: `width_pct` (della
  larghezza utile; altezza libera), `space_before_pt`, `space_after_pt`. Esempio: `plan` (le piante dei complessi).
  Una classe non definita nello stile e' segnalata in `anomalie.md` e la figura resta normale.
- Figure `{group=end}` consecutive: raggruppate come figure di fine sezione (in Word, griglia).

Migrazione dalle versioni precedenti (chiavi dello stile): `table.col_ratios` → `table.classes.finds` (con `markup: false`, `full_width: true`);
`images.plan_width_pct`, `plan_space_before_pt`, `plan_space_after_pt` → `images.classes.plan`.

## Plugin Obsidian

`obsidian-plugin/` contiene un plugin (solo desktop) che lancia il motore dal vault: comandi per impaginare il volume o il
capitolo della nota aperta (PDF, PDF con annotazioni, DOCX) e per aprire le anomalie. Installazione e impostazioni:
[obsidian-plugin/README.md](obsidian-plugin/README.md). Il motore espone `--json` (esito su stdout, il resto su stderr)
e `--list-chapters --json` proprio per questo.

## Installazione

Requisiti (testato con Python 3.12, Typst 0.15, pandoc 3.12): Python 3, [Typst](https://typst.app) (PDF), [pandoc](https://pandoc.org) (citazioni);
facoltativo Ghostscript (`gs`, riduzione del PDF).

    git clone https://github.com/lad-sapienza/volumen && cd volumen
    pip install -r requirements.txt
    brew install typst pandoc          # macOS; altrove: i pacchetti delle rispettive distribuzioni

- **Rete**: la prima volta Typst scarica il pacchetto `@preview/wrap-it` (figure con il testo intorno); serve la connessione,
  poi resta in cache.
- **Font**: il default è *Libertinus Serif*, incluso in Typst, quindi non serve installare nulla. Per usare altri font (nello
  stile, sezione «Font») devono essere installati sul computer; in Word valgono i font di Word.
- **Plugin Obsidian**: scarica `main.js` e `manifest.json` dall'ultima [release](../../releases) in
  `<vault>/.obsidian/plugins/volumen/` (nessun Node necessario) e indica nelle impostazioni la cartella di questo repo.
  Per sviluppare, invece, collega la cartella `obsidian-plugin/` e compila con `npm install && npm run build`.

## Uso

    python3 -m volumen                             # PDF con Typst (--keep-typ: salva anche il .typ per il debug; --no-pdf: solo il .typ)
    python3 -m volumen --shrink                    # + <nome>-shrink.pdf ridotto (Ghostscript; PRESET: screen|ebook|printer)
    python3 -m volumen --format docx               # DOCX (python-docx)
    python3 -m volumen --list-chapters             # id dei capitoli di volume.md
    python3 -m volumen --chapter 4                 # solo un capitolo (piu' veloce); anche --chapter 6.1 6.2
    python3 -m volumen --only F1-01 F5-07          # solo alcune schede del catalogo (prove)
    python3 -m volumen --set styles.normal.size=10.5 --set page.margin_interior=3

`--chapter ID [ID...]` impagina solo i capitoli scelti (un contenitore include i figli: `--chapter 6` =
tutta la parte 6). Il file esce con l'id nel nome (`<nome>-4.pdf`) salvo `--name`. I capitoli non
scelti non vengono impaginati; le cartelle di file (`source=<cartella>`) non vengono nemmeno lette. Le citazioni si
risolvono comunque su tutto il volume (lettere 2020a/b e bibliografia coincidono con il volume
completo). Numeri di pagina e delle note ripartono da 1.

## Controllo e test

    python3 -m volumen --validate              # controlla il volume senza impaginare: file e link mancanti, immagini, citazioni (scrive anomalie.md/.csv)
    python3 -m unittest discover -s tests -v   # test del motore

I test (`tests/`) usano un volume di prova (`tests/fixtures/mini`) e confrontano il sorgente Typst prodotto con
`tests/golden/mini.typ`. Dopo una modifica voluta dell'output: `UPDATE_GOLDEN=1 python3 -m unittest discover -s tests`, e si
rivede il diff del file golden. `VOLUMEN_TEST_COMPILE=1` compila anche il PDF vero (serve `typst`; la prima volta, la rete per il pacchetto `wrap-it`).
Alcuni test richiedono `pandoc` e si saltano se manca.

## Annotazioni (commenti di revisione)

Sintassi CriticMarkup nei Markdown, compatibile con i plugin di Obsidian:

```markdown
Il sito fu {==abbandonato nel IV sec.==}{>>Verificare con Rossi 2019<<} e poi riabitato.
Commento puntuale, senza testo evidenziato: {>>Aggiungere figura qui<<}
```

Senza flag le annotazioni **non compaiono** (il testo annotato resta normale: build finale). Con
`--annotations` diventano commenti Word (DOCX) e annotazioni PDF (Typst: evidenziazione + nota
apribile in Acrobat/Preview; il commento puntuale e' una nota adesiva). Autore, sigla e colore in
sezione «Stile» → `annotations`. Forme supportate: commento su un passo `{==..==}{>>..<<}`, commento puntuale `{>>..<<}` e i suggerimenti di
modifica `{++nuovo++}`, `{--vecchio--}`, `{~~vecchio~>nuovo~~}`. Con `--annotations` i suggerimenti sono visibili
(DOCX: vere modifiche tracciate di Word, con autore e data; PDF: vecchio barrato in rosso, nuovo sottolineato in verde);
senza flag restano nel testo solo se accettati: `annotations.suggestions` nello stile (`"accept"` = default,
`"reject"` = si tiene il testo vecchio). Nel PDF la nota puntuale sta nel margine destro, all'altezza del punto.

## La nota del volume (volume.md)

La composizione è una **nota Markdown** nella cartella dei contenuti (es. `.../MioVolume/md/volume.md`), da modificare in
Obsidian. L'eseguibile deve solo sapere dove sta: `--volume`, oppure la variabile `VOLUMEN_NOTE`, oppure un file `.volume` nel repo (una riga: il percorso; ignorato da git), oppure `./volume.md`. Contiene **struttura, indice e stile**; i titoli dei capitoli stanno nei loro file. La cartella di output è `output_dir` (relativa alla nota; default `out/` accanto alla nota).

```markdown
---
type: volume
title: Çuka e Ajtoit
authors: ["Nome Cognome | Affiliazione"]      # "Nome | Affiliazione" (l'affiliazione e' facoltativa)
lang: en-US
bibliography_title: References
toc: true                    # Typst: #outline; Word: campo (F9)
toc_depth: 2
toc_title: Contents
# toc_page_gap_cm: 1.5       # Typst: il testo di una voce va a capo almeno cosi' prima del numero di pagina
# toc_authors: true          # Typst: riga con gli autori sotto la voce del capitolo
list_of_figures: true        # opz.: list_of_figures_title / _size (8) / _columns / _separator (": ") / _gutter_cm
output_dir: out
output_name: mio-volume
images_dir: ../img           # radici comuni: percorsi assoluti o relativi alla nota
bibliography: ../bib/book.bib # export Zotero (Better BibLaTeX)
csl: ../styles/chicago-author-date-18th-edition-place.csl   # CSL nella cartella dei dati, non nel repo
# markdown_dir: .            # default: la cartella della nota
frontmatter: ["[title-page](title-page.md)", "[colophon](colophon.md)"]
---

- [preface](preface.md) {id=preface}                 # id non numerico: fuori dalla numerazione
- [02-previous-studies](02-previous-studies.md) {columns=2}
- Archaeology of Çuka e Ajtoit {divider}   # voce senza file, con figli: contenitore (pagina divisoria)
  - [06-01-introduction](06-01-introduction.md)
  - Complexes catalogue {source=complexes page_break_per_item series_order=F1,F2,F3 exclude_prefixes=BiS,NE}
  - [06-03-ceramics](06-03-ceramics.md) {bibliography=false}
```

- **Proprietà piatte**: il pannello Proprietà di Obsidian non gestisce oggetti annidati, quindi `toc: true` + `toc_depth: 2`
  al posto di `toc: {enabled, depth}`; `output_dir` / `output_name`; le chiavi non riconosciute restano disponibili come `{{chiave}}`.
- **Elenco dei capitoli**: ordine e indentazione = ordine e gerarchia. Una voce con link (`[testo](nome.md)`, oppure `[[nome]]` di Obsidian)
  è un capitolo Markdown; il nome si cerca accanto alla nota e poi in tutto il vault (cartella con `.obsidian`). Il testo
  e l'alias del link non contano: **il titolo viene solo dal campo `title` del file** (senza, il capitolo esce col numero
  e `anomalie.md` lo segnala). Il resto del corpo della nota (testo libero, titoli) è ignorato.
- **Opzioni per capitolo** nelle graffe finali, come per le immagini: `{chiave=valore chiave2="con spazi" flag}`; i flag
  senza valore valgono `true`; le liste usano la virgola (`series_order=F1,F2`). Chiavi: `columns`, `images`,
  `bibliography=false`, `running_title`, `new_page=false`, `numbered=false`, `divider`, `authors`, `base_level`.
- **Numerazione**: gli id si ricavano dalla posizione (`1`, `2`, ... e `5.1`, `5.2` nei figli) e sono quelli di `--chapter`,
  delle figure (`Fig. 5.2.1`) e dei titoli. `{id=...}` li fissa: un id **numerico** fa ripartire il conteggio da lì
  (`{id=3}` → il successivo è 4); uno **non numerico** (`{id=preface}`) toglie il capitolo dalla numerazione e dai titoli
  numerati senza spostare gli altri.
- **Cartella di file**: `Titolo {source=complexes ...}` = tutti i file Markdown della cartella `complexes` (relativa alla
  nota), un capitolo solo. Non ha figli. Opzioni: `series_order`, `exclude_prefixes`, `first`, `exclude`, `include`,
  `page_break_per_item`, `columns`, `id_field`. Va bene per qualsiasi cartella, anche scritta a mano.

### Chiavi del frontmatter

| Chiave | Default | Significato |
|---|---|---|
| `title` | – | titolo del volume (`{{title}}` nei blocchi di frontespizio) |
| `authors` | – | lista di `"Nome | Affiliazione"` (l'affiliazione è facoltativa); `{{authors}}` = nomi separati da virgola |
| `lang` | `en-US` | lingua (citazioni/bibliografia: pandoc) |
| `bibliography_title` | `References` | titolo della reference list in fondo a ogni capitolo |
| `toc` | `false` | `true`: indice (Typst `#outline`; Word campo da aggiornare con F9) |
| `toc_depth` | `2` | livelli di titolo nell'indice |
| `toc_title` | `Contents` | titolo dell'indice (solo Typst) |
| `toc_page_gap_cm` | `1.5` | Typst: spazio minimo fra il testo di una voce e il numero di pagina |
| `toc_authors` | `true` | Typst: riga con gli autori sotto la voce di un capitolo (stile `toc_author`) |
| `list_of_figures` | `false` | `true`: elenco di tutte le figure in fondo al volume (solo Typst) |
| `list_of_figures_title` | `List of Figures` | titolo dell'elenco |
| `list_of_figures_size` | `8` | corpo in pt |
| `list_of_figures_columns` | `2` | colonne |
| `list_of_figures_separator` | `": "` | fra numero e didascalia |
| `list_of_figures_gutter_cm` | `0.8` | distanza fra le colonne |
| `output_dir` | `out` | cartella di output; relativa alla nota (`--out` la scavalca) |
| `output_name` | `volume` | nome del file di output, senza estensione (`--name` lo scavalca) |
| `images_dir` | – | radice delle immagini; il default di un capitolo è `{images_dir}/{id}/` |
| `bibliography` | – | file `.bib` (export Zotero, Better BibLaTeX); senza, nessuna citazione viene risolta |
| `csl` | stile di pandoc | stile CSL delle citazioni |
| `markdown_dir` | cartella della nota | radice dei file Markdown; la risoluzione dei link guarda anche in tutto il vault |
| `frontmatter` | – | lista di link ai file di frontespizio/colophon (vedi «Frontespizio e colophon») |
| altre chiavi | – | disponibili come `{{chiave}}` nei blocchi di frontespizio (solo valori scalari) |

Percorsi: assoluti o relativi alla cartella della nota; `~` e `{id}` / `{images_dir}` sono espansi.

### Opzioni di capitolo

Nelle graffe dopo la voce. I valori non elencati sono passati ai sorgenti ma non hanno effetto.

| Opzione | Default | Vale per | Significato |
|---|---|---|---|
| `id=…` | dalla posizione | tutte | id esplicito (vedi «Numerazione») |
| `columns=N` | `1` | Markdown, cartelle | `2`+: capitolo (o testo delle voci) in un unico flusso a più colonne; solo Typst |
| `images=…` | `{images_dir}/{id}` | Markdown | cartella delle immagini del capitolo (cercate anche accanto al file `.md`) |
| `bibliography=false` | `true` | Markdown | niente reference list in fondo al capitolo |
| `running_title=…` | `title` del file | Markdown | testo dell'intestazione corrente (se manca anche `title`: l'id) |
| `new_page=false` | `true` | Markdown | il capitolo continua di seguito invece di iniziare su pagina nuova |
| `numbered=false` | `true` | tutte | niente numero davanti al titolo (vedi `chapter_numbering`) |
| `figure_prefix=…` | l'id del capitolo | Markdown | prefisso della numerazione di figure e tabelle (`Fig. <prefisso>.1`) |
| `base_level=N` | padre + 1 | tutte | livello del titolo del capitolo (1 = h1) |
| `authors="A,B"` | dal frontmatter del file | Markdown, cartelle | autori: riga sotto il titolo, indice, intestazione delle pagine pari |
| `divider` | `false` | contenitore | pagina divisoria con il solo titolo |
| `source=<cartella>` | – | cartelle | vedi «Cartella di file» |

Livelli dei titoli: un capitolo ha `base_level` = livello del padre + 1 (top level = h1); il suo titolo è a
quel livello, `##` nel Markdown a +1, `###` a +2, fino a h5. Uno stile `hN` mancante nello stile
ripiega sul livello definito più vicino sopra.

## Frontespizio e colophon (frontmatter)

Nella nota `volume.md`, chiave `frontmatter`, prima dell'indice, una lista di link ai file Markdown; ognuno inizia una pagina nuova:

```yaml
frontmatter: ["[title-page](title-page.md)", "[colophon](colophon.md)"]   # frontespizio (pagina destra), colophon (verso)
```

Le pagine di frontmatter non hanno intestazione né numero e non entrano nella numerazione: l'indice (o il primo
capitolo) parte sulla prima pagina destra e lì la numerazione riparte da `header.start_page`. In ogni file `---` su una
riga da sola significa «nuova pagina». Non si caricano con `--chapter`. Valgono PDF Typst e DOCX.

Ogni blocco si stila con un divisore Pandoc; i valori fra graffe sono tutti facoltativi:

```markdown
::: {font="Arno Pro" size=34 weight=bold align=center margin-top=5cm}
{{title}}
:::

::: {.sottotitolo size=16 italic=true margin-top=1cm}
Archaeological survey
:::
```

- `.nome` richiama uno stile di `styles` (sezione «Stile») (anche uno nuovo, es. `styles.sottotitolo`); gli attributi lo
  modificano per quel blocco. Senza stile con nome la base è `normal` senza rientro, a sinistra e senza spazi.
- Attributi: `font`, `size` (pt; l'interlinea segue il corpo, salvo `line-height`), `weight` (`regular|bold|600`), `italic`,
  `color` (esadecimale), `align` (`left|center|right|justify`), `margin-top`, `margin-bottom`, `line-height`, `indent`
  (prima riga), `tracking` (spaziatura fra le lettere), `case` (`upper|lower|smallcaps`), `width` (larghezza del blocco: `8cm`, `60%`; il blocco sta a sinistra/al centro/a destra secondo `align`, il testo è allineato dentro). Unità: `cm`, `mm`, `in`, `pt`, `em`
  (senza unità = pt). Più paragrafi nello stesso blocco condividono lo stile; `margin-top` vale una volta, in testa.
- `{{chiave}}` prende i valori scalari del frontmatter di `volume.md` (`{{title}}`, `{{year}}`, ...) e `{{authors}}` (nomi separati da
  virgola). Le chiavi mancanti restano e sono segnalate in `anomalie.md`.
- Un'immagine, anche dentro un blocco `::: {...}` (`![](logo.png){width=4cm align=left}`), non ha numero né didascalia; senza `width`/`height` ha la dimensione naturale a 96 dpi (mai ingrandita) e `align` (default: quello del blocco in cui sta, altrimenti centro).
- I blocchi `::: {...}` funzionano in qualsiasi capitolo Markdown.

## Capitoli Markdown

Un file per capitolo. Frontmatter opzionale:

```yaml
---
title: Titolo del capitolo          # il titolo del capitolo viene solo da qui (senza: l'id)
authors: [Nome Cognome, ...]        # riga grigia sotto il titolo di apertura
running_title: Titolo breve
---
```

Sintassi supportata:

| Cosa | Sintassi |
|---|---|
| titoli | `##` (a +1 dal capitolo), `###`, ... fino a h5 |
| enfasi | `*corsivo*`, `_corsivo_`, `**grassetto**`, apice `18^th^` |
| barrato | `~~testo~~` |
| evidenziato | `==testo==` oppure `[testo]{.mark}` (colore: `typography.highlight_color`) |
| citazioni | `> testo` e, come ultima riga, `> — riferimento` |
| elenchi | `-`, `*`, `1.` (annidati per rientro di 2 spazi) |
| tabelle | pipe, con riga `\| --- \|` (anche `:---`, `---:`); didascalia opzionale `Table: testo {#tab-x}` |
| note | `[^1]` nel testo e `[^1]: testo` (anche su piu' righe rientrate) |
| citazioni bibliografiche | `[@chiave, 49]`, `[@a; @b]` (fra le opere il `;`), `@chiave` narrativa, `[-@chiave]` |
| figure | `![didascalia](file.jpg){#etichetta width=60% position=top}` |
| riferimenti interni | `[Fig.](#etichetta)` → "Fig. 4.2" (figure e tabelle dello stesso capitolo) |
| link | `[testo](https://...)` → resta il testo |

Le figure sono numerate `Fig. <id capitolo>.N.` (le tabelle `Table <id>.N.`). Il codice non corregge: se una
didascalia contiene già "Fig. 2." lo segnala. I Markdown esportati da Word/Pandoc (didascalie su piu'
righe, ancore `[]{#_Ref...}`, escape `\[`, tabelle su una riga, `--` al posto di `---`) sono tollerati.

### Attributi per figura

    ![Didascalia](file.jpg){#fig-x width=60% height=8cm position=right wrap=2}

- `width` / `height`: `12cm`, `5in`, `300px`, `60%` (della larghezza utile, o della colonna con `column|left|right`).
  Scavalcano i tetti `images.max_*` / `images.flow_max_height_cm`. Valgono anche in Word.
- `position` (solo PDF Typst): `left` / `right` = il testo scorre intorno alla figura, a 1 colonna e nei
  capitoli a colonne (pacchetto `wrap-it`, scaricato al primo uso); `wrap=N` = paragrafi seguenti che girano
  intorno. Con `width` alto (oltre ~60%) la colonna di testo diventa molto stretta. Nei capitoli a colonne
  valgono anche `auto` (default), `top`, `bottom` = figura flottante a piena larghezza e `column` =
  flottante dentro la colonna.
- Nei capitoli a due colonne le figure sono flottanti (cima/fondo pagina) per non lasciare buchi;
  `images.flow_max_height_cm` limita l'altezza cosi' che due figure sulla stessa pagina lascino testo.

### Citazioni bibliografiche

Le citazioni `[@chiave]` sono risolte da `pandoc --citeproc` con `sources.bibliography` e `sources.csl`
(qui Chicago autore-data); in fondo a ogni capitolo compare la sua *References*, solo con le opere citate.
Una chiave assente dal `.bib` o una `,` prima di un altro `@chiave` (serve `;`) vengono segnalate in
`anomalie.md`, senza correzioni automatiche.

Lo stile CSL non fa parte del repo: sta nella cartella dei dati (`styles/`). Si usa il CMOS 18 autore-data
ufficiale (da Zotero) con **una sola modifica**: decommentata la riga `publisher-place` nella macro
`source-publication-publisher-bib`, cosi' le monografie escono come `Citta': Editore` (il 18 la omette di
default). Nessun `———` per l'autore ripetuto. La citta' compare solo se `location`/`address` e' compilato nel `.bib`.

## Cartelle di file (`source=<cartella>`)

`source=<cartella>` legge i file; l'ID di una voce e' il nome del file senza `.md` (se `id_field` e' dato, quel campo del front matter). Sceglie quali includere e in che ordine con `series_order`, `exclude_prefixes` e le
eccezioni `first` / `exclude` / `include`; ordine naturale degli ID dentro ogni serie. `page_break_per_item`,
`columns` e le figure di fine scheda (`{group=end}`, sempre in fondo alla voce) restano impostazioni di volume.

**Link a una scheda** da un capitolo Markdown: `[F1-02](F1-02.md)` (sintassi `[testo](file.md)`; vale anche `[[F1-02]]`). Si legge «F1-02» ed è cliccabile nel PDF, senza colore né sottolineatura (`links` nello stile).
Funziona solo per le schede incluse nel volume: se il file non esiste, la serie è esclusa o la scheda non è pubblicata, il
link è segnalato in `anomalie.md` come «link a capitolo non risolto» e resta il solo testo.

## Stile (blocchi yaml di volume.md)

Nella nota del volume, sotto un titolo (es. `## Stile`), uno o più blocchi ` ```yaml ` con le chiavi qui sotto; Obsidian
li colora e i titoli si possono comprimere. Tutti i blocchi si uniscono, e quel che manca usa i **default** indicati
(nessuna chiave è obbligatoria: una nota senza stile produce un volume completo, in Libertinus Serif 11 pt (il font libero incluso in Typst)). Gli strati, dal più
basso: blocchi di `volume.md` → `--config file.yaml|json` (opzionale) → `--set chiave=valore` (es. `--set styles.normal.size=10.5`).
Le voci `- ...` dentro un blocco non sono capitoli. Un errore di YAML ferma la build indicando la riga.
Nelle tabelle: **T** = solo PDF Typst, **W** = solo Word, altrimenti vale per entrambi.

### styles: gli stili di paragrafo

`styles.<nome>` è un dizionario di queste chiavi (quelle mancanti ripiegano sullo stile indicato, poi sui default):

| Chiave | Default | Significato |
|---|---|---|
| `font` | `Libertinus Serif` | famiglia (se non è installata Typst/Word ne sostituiscono un'altra) |
| `size` | `11` | corpo in pt |
| `bold`, `italic` | `false` | |
| `color` | `000000` | esadecimale, senza `#` (quotato in YAML: `'000000'`) |
| `line_height` | `size × 1.2` | passo di riga in **pt**, identico in Word e Typst |
| `first_line_indent` | `0` | rientro della prima riga, pt (negativo = sporgente) |
| `indent_left`, `indent_right` | `0` | rientri laterali, pt |
| `space_before`, `space_after` | `0` | spazi sopra/sotto, pt |
| `align` | `left` | `left`, `center`, `right`, `justify` |
| `paragraph_gap` | `4` | solo `quote`: spazio fra i paragrafi della citazione, pt |
| `keep_together_chars` | `700` | solo `quote` (T): una citazione più corta di questi caratteri non si spezza fra pagine |

Gli stili usati e il loro ripiego (se non definiti):

| Stile | Per cosa | Ripiego |
|---|---|---|
| `h1` … `h5` | titoli (h1 = capitolo); uno `hN` mancante usa il livello definito più vicino sopra | `h1` |
| `normal` | testo | default sopra |
| `caption` | didascalie di figure e tabelle | – |
| `quote` | citazioni `> testo` | `normal` |
| `list` | elenchi | `normal` |
| `footnote` | note a piè di pagina | `normal` |
| `bibliography` | voci della reference list | `normal` |
| `chapter_author` | riga degli autori sotto il titolo del capitolo | `normal` |
| `toc_author` | riga degli autori nell'indice (T) | `chapter_author` |
| `table_header`, `table_body` | intestazione e celle delle tabelle | – |
| `header_title`, `header_pagenum` | intestazione corrente: titolo e numero di pagina | – |
| *qualsiasi altro nome* | si richiama con `::: {.nome}` (vedi «Frontespizio e colophon») | `normal` |

### page, header, chapter_opener, chapter_numbering

| Chiave | Default | Significato |
|---|---|---|
| `page.size` | `A4` | `A4` oppure `Letter` |
| `page.margin_top_cm`, `page.margin_bottom_cm` | `2.5` | margini sopra e sotto |
| `page.margin_interior`, `page.margin_exterior` | `2.5` | margini **speculari** (interno = lato rilegatura), cm; per margini non speculari `margin_left_cm` / `margin_right_cm` (default 2.5) |
| `page.page_numbers` | `true` | numero di pagina nell'intestazione |
| `page.chapter_start` | `right` | T: `right` = ogni capitolo inizia in una pagina destra (se serve si inserisce una pagina vuota senza intestazione); `any` = di seguito |
| `header.enabled` | `true` | intestazione corrente: pagine dispari titolo (verso l'interno) e numero (verso l'esterno), pagine pari specchiate |
| `header.title` | – | testo di ripiego quando il capitolo non ha né `running_title` né `title` |
| `header.left_pages` | `author` | testo delle pagine pari: `author` = autori del capitolo (altrimenti del volume), `title` = come le pagine dispari |
| `header.start_page` | `1` | numero della prima pagina dopo il frontespizio |
| `header.skip_chapter_first_page` | `true` | niente intestazione nella prima pagina di ogni capitolo e sulle divisorie |
| `header.rule.enabled` | `true` | filetto sotto l'intestazione |
| `header.rule.color` | `000000` | |
| `header.rule.size_eighths_pt` | `4` | spessore in ottavi di pt |
| `header.rule.space_pt` | `2` | spazio fra testo e filetto |
| `chapter_opener.offset_pct` | `33` | il titolo h1 di un capitolo parte a questa percentuale dell'altezza di pagina |
| `chapter_numbering` | `true` | antepone ai titoli il numero del capitolo preso dall'id (`6.` per i capitoli, `6.1` per i sotto-capitoli); un titolo già numerato a mano non viene toccato; un id non numerico (`{id=preface}`) o `numbered=false` esclude il capitolo |

### table

| Chiave | Default | Significato |
|---|---|---|
| `table.empty_cell` | `–` | testo delle celle vuote (tutte le tabelle del volume) |
| `table.rule_pt` | `0.75` | spessore dei filetti sopra e sotto la tabella |
| `table.header_rule_pt` | `0.5` | spessore del filetto sotto l'intestazione (che si ripete a ogni pagina) |
| `table.space_after_pt` | `14` | spazio dopo la tabella |
| `table.classes.<nome>` | – | classi `{.nome}`: `col_ratios` (pesi delle colonne), `markup` (default `true`; `false`: le celle non interpretano `**`/`*`), `empty_cell`, `full_width` (T: mai fluttuante) |

Le tabelle con più di 20 righe sono sempre a piena larghezza; le più brevi, nei capitoli a colonne, fluttuano a piena larghezza.

### images

| Chiave | Default | Significato |
|---|---|---|
| `images.max_width_cm`, `images.max_height_cm` | `15`, `20` | tetti alle dimensioni di una figura (scavalcati da `width`/`height` della figura) |
| `images.figure_space_before_pt` | `4` | spazio sopra una figura |
| `images.figure_space_after_pt` | – | spazio sotto (senza: quello dello stile `caption`) |
| `images.min_caption_cm` | `5` | T: larghezza minima della didascalia (altrimenti è larga come l'immagine) |
| `images.float_position` | `auto` | T, capitoli a colonne: `auto`, `top`, `bottom` (posizione delle figure fluttuanti) |
| `images.flow_max_height_cm` | = `max_height_cm` | T, capitoli a colonne: tetto all'altezza delle figure fluttuanti, perché due figure sulla stessa pagina lascino testo |
| `images.wrap_width_cm` | `5` | T: larghezza di una figura `position=left|right` senza `width` |
| `images.wrap_gutter_pt` | `12` | T: distanza fra figura e testo che le scorre intorno |
| `images.figures_landscape_per_page` | – | W: quante figure orizzontali per pagina nelle sezioni di figure (senza: altezza massima `max_height_cm`) |
| `images.figures_row_reserve_cm` | `1.2` | W: spazio riservato per riga nelle sezioni di figure |
| `images.classes.<nome>` | – | classi `{class=nome}`: `width_pct` (della larghezza utile; altezza libera; default 100), `space_before_pt`, `space_after_pt` (default come `figure_space_before_pt`) |

### typst, links, typography, annotations

| Chiave | Default | Significato |
|---|---|---|
| `typst.column_gutter_cm` | `1.0` | distanza fra le colonne |
| `typst.flow_heading_min_level` | `3` | i titoli di questo livello in poi, fra due testi a colonne (es. Material Culture), restano nel flusso delle colonne |
| `typst.balance_columns_max` | `0.5` | i testi a due colonne più corti di questa frazione di pagina sono bilanciati (0 = disattivato) |
| `typst.balance_min_flow` | `0.2` | se non entrano nello spazio rimasto, scorrono comunque nelle colonne se resta almeno questa frazione di pagina; altrimenti passano alla pagina dopo |
| `links.color` | `null` | colore dei link tra capitoli (esadecimale); `null` = come il testo (per la stampa) |
| `links.underline`, `links.bold` | `false` | |
| `typography.hyphenate` | `false` | `true`: sillabazione automatica |
| `typography.highlight_color` | `FFEB3B` | colore di `==evidenziato==` |
| `annotations.enabled` | `false` | come `--annotations` (commenti Word / annotazioni PDF) |
| `annotations.author`, `annotations.initials` | `Autore`, vuoto | autore e sigla dei commenti |
| `annotations.color` | `FFD54F` | colore delle annotazioni |
| `annotations.suggestions` | `accept` | senza `--annotations`: `accept` = resta il testo nuovo di `{++ ++}`/`{~~ ~> ~~}`, `reject` = il vecchio |

### Esempio completo

```yaml
page: {size: A4, margin_top_cm: 3.5, margin_bottom_cm: 2.5, margin_interior: 4, margin_exterior: 3}
styles:
  h1: {font: Arno Pro, size: 20, align: center, line_height: 26, space_after: 20}
  normal: {font: Minion Pro, size: 11, line_height: 13, first_line_indent: 12, align: justify}
  caption: {font: Minion Pro, size: 9, italic: true, align: center}
table: {empty_cell: "–", classes: {finds: {col_ratios: [16, 14, 10, 9, 7, 7, 7, 9, 6], markup: false, full_width: true}}}
images: {max_width_cm: 14, classes: {plan: {width_pct: 100, space_before_pt: 20, space_after_pt: 16}}}
header: {title: Çuka e Ajtoit, left_pages: author, rule: {size_eighths_pt: 4}}
typography: {hyphenate: false}
```

### Font

I font sono quelli installati sul computer (qui: Arno Pro per i titoli, Minion Pro per il testo). Se un font non c'è, Typst e Word ne
sostituiscono un altro.

## Differenze fra i due formati

Il PDF Typst è il formato di consegna; il DOCX segue le stesse regole ma non ha: colonne, figure flottanti, testo
che scorre intorno, `position`. Le note sono vere note Word; l'indice Word è un campo da aggiornare (F9).
