# Volumen by LAD

Typesets a volume from Markdown notes (Obsidian/Zotero): chapters, folders of entries, bibliography → **PDF with
Typst** (delivery format) and **DOCX** (working format). Composition and style live in a single note, `volume.md`.
There is an [Obsidian plugin](obsidian-plugin/README.md) that runs the engine from the vault.

The engine only does layout: it never corrects data or texts, it reports problems in `anomalies.md` / `.csv`.

The engine reads only Markdown files: no network, no database. A folder of Markdown files (`source=<folder>`) can be
composed as a catalogue of entries.

A complete volume to try right away is in [`example/`](example/md/volume.md) (Samuel Butler's 1900 translation of the
*Odyssey*, public domain): `python3 -m volumen --volume example/md/volume.md`.

## Structure

A single file for composition and style:

| File | Contains |
|---|---|
| `volume.md` | **the whole volume**: title, authors, table of contents, chapters (a list of links to files), paths, bibliography and **style** (`yaml` blocks). An Obsidian note **next to the Markdown content files**, not in this repository |

Code: the **engine** = `volumen/sources/*` (`markdown`; `folder` = a folder of Markdown files, one file per entry) produces
the blocks of the model (`volumen/model.py`); `volumen/render/typst.py` and `volumen/render/docx.py` typeset them;
`volumen/citations.py` resolves citations with pandoc. The engine only reads Markdown. Single entry point:
`python3 -m volumen`.

### Table and figure classes (style)

Markdown never carries measures: you mark a block with a **class** and the style (the "Style" section of `volume.md`)
says what it looks like.

- Table: a `{.name}` line right after the table → `table.classes.<name>`: `col_ratios` (column weights),
  `markup` (`false`: cells do not interpret `**`/`*`), `empty_cell`, `full_width` (Typst: never floating, full width).
  Example: `{.finds}` (a table of finds).
- Figure: attribute `{class=name}` (or the legacy name `role=name`) → `images.classes.<name>`: `width_pct` (of the
  usable width; free height), `space_before_pt`, `space_after_pt`. Example: `plan` (floor plans).
  A class not defined in the style is reported in `anomalies.md` and the figure stays normal.
- Consecutive `{group=end}` figures: grouped as end-of-section figures (a grid in Word).

Migration from earlier versions (style keys): `table.col_ratios` → `table.classes.finds` (with `markup: false`,
`full_width: true`); `images.plan_width_pct`, `plan_space_before_pt`, `plan_space_after_pt` → `images.classes.plan`.

## Obsidian plugin

`obsidian-plugin/` contains a plugin (desktop only) that runs the engine from the vault: commands to typeset the volume or
the chapter of the open note (PDF, PDF with annotations, DOCX) and to open the anomalies. Installation and settings:
[obsidian-plugin/README.md](obsidian-plugin/README.md). The engine exposes `--json` (result on stdout, everything else on
stderr) and `--list-chapters --json` for exactly this purpose.

## Installation

Requirements (tested with Python 3.12, Typst 0.15, pandoc 3.12): Python 3, [Typst](https://typst.app) (PDF),
[pandoc](https://pandoc.org) (citations); optionally Ghostscript (`gs`, PDF size reduction).

    git clone https://github.com/lad-sapienza/volumen && cd volumen
    pip install -r requirements.txt
    brew install typst pandoc          # macOS; elsewhere: the packages of your distribution

- **Network**: the first time, Typst downloads the `@preview/wrap-it` package (figures with text flowing around them); a
  connection is needed, then it stays in the cache.
- **Fonts**: the default is *Libertinus Serif*, bundled with Typst, so nothing needs to be installed. To use other fonts
  (in the style, "Font" section) they must be installed on the computer; Word uses the fonts available to Word.
- **Obsidian plugin**: download `main.js` and `manifest.json` from the latest [release](../../releases) into
  `<vault>/.obsidian/plugins/volumen/` (no Node needed) and set the folder of this repository in the plugin settings.
  For development, link the `obsidian-plugin/` folder instead and build with `npm install && npm run build`.

## Usage

    python3 -m volumen                             # PDF with Typst (--keep-typ: also keep the .typ for debugging; --no-pdf: only the .typ)
    python3 -m volumen --shrink                    # + <name>-shrink.pdf, reduced (Ghostscript; PRESET: screen|ebook|printer)
    python3 -m volumen --format docx               # DOCX (python-docx)
    python3 -m volumen --list-chapters             # chapter ids of volume.md
    python3 -m volumen --chapter 4                 # only one chapter (faster); also --chapter 6.1 6.2
    python3 -m volumen --only F1-01 F5-07          # only some entries of a folder (tests)
    python3 -m volumen --set styles.normal.size=10.5 --set page.margin_interior=3

`--chapter ID [ID...]` typesets only the chosen chapters (a container includes its children: `--chapter 6` = the whole
part 6). The file gets the id in its name (`<name>-4.pdf`) unless `--name` is given. The other chapters are not
typeset; folders of files (`source=<folder>`) are not even read. Citations are still resolved over the whole volume
(letters such as 2020a/b and the bibliography match the complete volume). Page and note numbers restart from 1.

## Checks and tests

    python3 -m volumen --validate              # checks the volume without typesetting: missing files and links, images, citations (writes anomalies.md/.csv)
    python3 -m unittest discover -s tests -v   # engine tests

The tests (`tests/`) use a test volume (`tests/fixtures/mini`) and compare the Typst source produced with
`tests/golden/mini.typ`. After an intended change of the output: `UPDATE_GOLDEN=1 python3 -m unittest discover -s tests`,
then review the diff of the golden file. `VOLUMEN_TEST_COMPILE=1` also compiles the real PDF (needs `typst`; the first
time, the network for the `wrap-it` package). Some tests need `pandoc` and are skipped if it is missing.

## Annotations (review comments)

CriticMarkup syntax in the Markdown files, compatible with Obsidian plugins:

```markdown
The site was {==abandoned in the 4th century==}{>>Check with Rossi 2019<<} and then reoccupied.
A point comment, without highlighted text: {>>Add figure here<<}
```

Comments may carry attributes (`{date="2026-10-06">>text<<}`), as written by some track-changes plugins; the attributes
are ignored.

Without the flag annotations **do not appear** (the annotated text stays normal: final build). With `--annotations`
they become Word comments (DOCX) and PDF annotations (Typst: highlight + a note that opens in Acrobat/Preview; the point
comment is a sticky note). Author, initials and colour are in the "Style" section → `annotations`. Supported forms: a
comment on a passage `{==..==}{>>..<<}`, a point comment `{>>..<<}` and edit suggestions `{++new++}`, `{--old--}`,
`{~~old~>new~~}`. With `--annotations` suggestions are visible (DOCX: real Word tracked changes, with author and date;
PDF: old text struck through in red, new text underlined in green); without the flag only the accepted text stays:
`annotations.suggestions` in the style (`"accept"` = default, `"reject"` = keep the old text). In the PDF the point note
sits in the right margin, level with the spot.

## The volume note (volume.md)

The composition is a **Markdown note** in the content folder (e.g. `.../MyVolume/md/volume.md`), edited in Obsidian. The
executable only needs to know where it is: `--volume`, or the `VOLUMEN_NOTE` environment variable, or a `.volume` file
in the repository (one line: the path; ignored by git), or `./volume.md`. It holds **structure, table of contents and
style**; chapter titles live in their own files. The output folder is `output_dir` (relative to the note; default `out/`
next to the note).

```markdown
---
type: volume
title: The Odyssey
authors: ["First Last | Affiliation"]         # "Name | Affiliation" (the affiliation is optional)
lang: en-US
bibliography_title: References
toc: true                    # Typst: #outline; Word: field (F9)
toc_depth: 2
toc_title: Contents
# toc_page_gap_cm: 1.5       # Typst: the text of an entry wraps at least this far before the page number
# toc_authors: true          # Typst: line with the authors under the chapter entry
list_of_figures: true        # optional: list_of_figures_title / _size (8) / _columns / _separator (": ") / _gutter_cm
output_dir: out
output_name: my-volume
images_dir: ../img           # common roots: absolute paths or relative to the note
bibliography: ../bib/book.bib # Zotero export (Better BibLaTeX)
csl: ../styles/chicago-author-date-18th-edition-place.csl   # CSL in the data folder, not in the repository
# markdown_dir: .            # default: the folder of the note
frontmatter: ["[title-page](title-page.md)", "[colophon](colophon.md)"]
---

- [preface](preface.md) {id=preface}                 # non-numeric id: outside the numbering
- [02-previous-studies](02-previous-studies.md) {columns=2}
- Archaeology of the site {divider}   # entry without a file, with children: container (divider page)
  - [06-01-introduction](06-01-introduction.md)
  - Catalogue of complexes {source=complexes page_break_per_item series_order=F1,F2,F3 exclude_prefixes=BiS,NE}
  - [06-03-ceramics](06-03-ceramics.md) {bibliography=false}
```

- **Flat properties**: Obsidian's Properties panel does not handle nested objects, so `toc: true` + `toc_depth: 2` instead
  of `toc: {enabled, depth}`; `output_dir` / `output_name`; unrecognised keys stay available as `{{key}}`.
- **Chapter list**: order and indentation = order and hierarchy. An entry with a link (`[text](name.md)`, or Obsidian's
  `[[name]]`) is a Markdown chapter; the name is looked up next to the note and then in the whole vault (folder with
  `.obsidian`). The text and alias of the link do not matter: **the title comes only from the file's `title` field**
  (without it, the chapter appears with its number and `anomalies.md` reports it). The rest of the note's body (free text,
  headings) is ignored.
- **Per-chapter options** in the trailing braces, as for images: `{key=value key2="with spaces" flag}`; flags without a
  value mean `true`; lists use a comma (`series_order=F1,F2`). Keys: `columns`, `images`, `bibliography=false`,
  `running_title`, `new_page=false`, `numbered=false`, `divider`, `authors`, `base_level`.
- **Numbering**: ids come from the position (`1`, `2`, ... and `5.1`, `5.2` for children) and are the ones used by
  `--chapter`, by figures (`Fig. 5.2.1`) and by headings. `{id=...}` fixes them: a **numeric** id restarts the count from
  there (`{id=3}` → the next is 4); a **non-numeric** one (`{id=preface}`) removes the chapter from the numbering and from
  numbered headings without shifting the others.
- **Folder of files**: `Title {source=complexes ...}` = all Markdown files of the `complexes` folder (relative to the
  note), as a single chapter. It has no children. Options: `series_order`, `exclude_prefixes`, `first`, `exclude`,
  `include`, `page_break_per_item`, `columns`, `id_field`. Works for any folder, even one written by hand.

### Frontmatter keys

| Key | Default | Meaning |
|---|---|---|
| `title` | – | volume title (`{{title}}` in title-page blocks) |
| `authors` | – | list of `"Name | Affiliation"` (the affiliation is optional); `{{authors}}` = names separated by commas |
| `lang` | `en-US` | language (citations/bibliography: pandoc) |
| `bibliography_title` | `References` | title of the reference list at the end of each chapter |
| `toc` | `false` | `true`: table of contents (Typst `#outline`; Word field to update with F9) |
| `toc_depth` | `2` | heading levels in the table of contents |
| `toc_title` | `Contents` | title of the table of contents (Typst only) |
| `toc_page_gap_cm` | `1.5` | Typst: minimum space between the text of an entry and the page number |
| `toc_authors` | `true` | Typst: line with the authors under a chapter entry (style `toc_author`) |
| `list_of_figures` | `false` | `true`: list of all figures at the end of the volume (Typst only) |
| `list_of_figures_title` | `List of Figures` | title of the list |
| `list_of_figures_size` | `8` | font size in pt |
| `list_of_figures_columns` | `2` | columns |
| `list_of_figures_separator` | `": "` | between number and caption |
| `list_of_figures_gutter_cm` | `0.8` | distance between columns |
| `output_dir` | `out` | output folder; relative to the note (`--out` overrides it) |
| `output_name` | `volume` | output file name, without extension (`--name` overrides it) |
| `images_dir` | – | root of the images; a chapter's default is `{images_dir}/{id}/` |
| `bibliography` | – | `.bib` file (Zotero export, Better BibLaTeX); without it, no citation is resolved |
| `csl` | pandoc's style | CSL style of the citations |
| `markdown_dir` | folder of the note | root of the Markdown files; link resolution also looks in the whole vault |
| `frontmatter` | – | list of links to the title-page/colophon files (see "Title page and colophon") |
| other keys | – | available as `{{key}}` in title-page blocks (scalar values only) |

Paths: absolute or relative to the note's folder; `~` and `{id}` / `{images_dir}` are expanded.

### Chapter options

In the braces after the entry. Values not listed are passed to the sources but have no effect.

| Option | Default | Applies to | Meaning |
|---|---|---|---|
| `id=…` | from the position | all | explicit id (see "Numbering") |
| `columns=N` | `1` | Markdown, folders | `2`+: chapter (or the text of entries) in a single multi-column flow; Typst only |
| `images=…` | `{images_dir}/{id}` | Markdown | folder of the chapter's images (also searched next to the `.md` file) |
| `bibliography=false` | `true` | Markdown | no reference list at the end of the chapter |
| `running_title=…` | the file's `title` | Markdown | text of the running head (if `title` is missing too: the id) |
| `new_page=false` | `true` | Markdown | the chapter continues instead of starting on a new page |
| `numbered=false` | `true` | all | no number before the title (see `chapter_numbering`) |
| `figure_prefix=…` | the chapter id | Markdown | prefix of figure and table numbering (`Fig. <prefix>.1`) |
| `base_level=N` | parent + 1 | all | heading level of the chapter title (1 = h1) |
| `authors="A,B"` | from the file's frontmatter | Markdown, folders | authors: line under the title, table of contents, running head of even pages |
| `divider` | `false` | container | divider page with the title only |
| `source=<folder>` | – | folders | see "Folder of files" |

Heading levels: a chapter has `base_level` = parent's level + 1 (top level = h1); its title is at that level, `##` in
the Markdown at +1, `###` at +2, up to h5. A missing `hN` style falls back to the nearest defined level above.

## Title page and colophon (frontmatter)

In the `volume.md` note, key `frontmatter`, before the table of contents, a list of links to Markdown files; each starts
a new page:

```yaml
frontmatter: ["[title-page](title-page.md)", "[colophon](colophon.md)"]   # title page (right page), colophon (verso)
```

Frontmatter pages have no running head and no number and are outside the numbering: the table of contents (or the first
chapter) starts on the first right-hand page, and the numbering restarts there from `header.start_page`. In each file, `---`
on a line by itself means "new page". They are not loaded with `--chapter`. Valid for Typst PDF and DOCX.

Each block is styled with a Pandoc div; the values between braces are all optional:

```markdown
::: {font="Arno Pro" size=34 weight=bold align=center margin-top=5cm}
{{title}}
:::

::: {.subtitle size=16 italic=true margin-top=1cm}
Archaeological survey
:::
```

- `.name` calls a style of `styles` ("Style" section) (also a new one, e.g. `styles.subtitle`); the attributes modify it
  for that block. Without a named style the base is `normal` with no indent, left-aligned and with no spacing.
- Attributes: `font`, `size` (pt; the leading follows the size, unless `line-height`), `weight` (`regular|bold|600`),
  `italic`, `color` (hexadecimal), `align` (`left|center|right|justify`), `margin-top`, `margin-bottom`, `line-height`,
  `indent` (first line), `tracking` (letter spacing), `case` (`upper|lower|smallcaps`), `width` (block width: `8cm`,
  `60%`; the block sits left/centre/right according to `align`, the text is aligned inside). Units: `cm`, `mm`, `in`,
  `pt`, `em` (no unit = pt). Several paragraphs in the same block share the style; `margin-top` applies once, at the top.
- `{{key}}` takes the scalar values of the `volume.md` frontmatter (`{{title}}`, `{{year}}`, ...) and `{{authors}}`
  (names separated by commas). Missing keys stay as they are and are reported in `anomalies.md`.
- An image, also inside a `::: {...}` block (`![](logo.png){width=4cm align=left}`), has no number and no caption;
  without `width`/`height` it has its natural size at 96 dpi (never enlarged) and `align` (default: that of the block
  it is in, otherwise centre).
- `::: {...}` blocks work in any Markdown chapter.

## Markdown chapters

One file per chapter. Optional frontmatter:

```yaml
---
title: Chapter title                # the chapter title comes only from here (without it: the id)
authors: [First Last, ...]          # grey line under the opening title
running_title: Short title
---
```

Supported syntax:

| What | Syntax |
|---|---|
| headings | `##` (at +1 from the chapter), `###`, ... up to h5 |
| emphasis | `*italic*`, `_italic_`, `**bold**`, superscript `18^th^` |
| strikethrough | `~~text~~` |
| highlight | `==text==` or `[text]{.mark}` (colour: `typography.highlight_color`) |
| quotations | `> text` and, as the last line, `> — reference` |
| lists | `-`, `*`, `1.` (nested by a 2-space indent) |
| tables | pipes, with a `\| --- \|` row (also `:---`, `---:`); optional caption `Table: text {#tab-x}` |
| footnotes | `[^1]` in the text and `[^1]: text` (also over several indented lines) |
| bibliographic citations | `[@key, 49]`, `[@a; @b]` (`;` between works), narrative `@key`, `[-@key]` |
| figures | `![caption](file.jpg){#label width=60% position=top}` |
| internal references | `[Fig.](#label)` → "Fig. 4.2" (figures and tables of the same chapter) |
| links to other chapters | `[text](file.md)` → the chapter number, clickable in the PDF; `[](file.md)` shows only the number |
| links | `[text](https://...)` → only the text remains |

Figures are numbered `Fig. <chapter id>.N.` (tables `Table <id>.N.`). The engine does not correct: if a caption already
contains "Fig. 2." it reports it. Markdown exported from Word/Pandoc (multi-line captions, `[]{#_Ref...}` anchors, `\[`
escapes, one-line tables, `--` instead of `---`) is tolerated. A link written without the `.md` extension
(`[text](slug)`) is not resolved and is reported.

### Figure attributes

    ![Caption](file.jpg){#fig-x width=60% height=8cm position=right wrap=2}

- `width` / `height`: `12cm`, `5in`, `300px`, `60%` (of the usable width, or of the column with `column|left|right`).
  They override the `images.max_*` / `images.flow_max_height_cm` ceilings. Valid in Word too.
- `position` (Typst PDF only): `left` / `right` = the text flows around the figure, in 1 column and in multi-column
  chapters (`wrap-it` package, downloaded on first use); `wrap=N` = following paragraphs that wrap around it. With a large
  `width` (over ~60%) the text column becomes very narrow. In multi-column chapters `auto` (default), `top`, `bottom` =
  floating figure at full width and `column` = floating inside the column are also valid.
- In two-column chapters figures float (top/bottom of the page) so as not to leave gaps; `images.flow_max_height_cm`
  limits the height so that two figures on the same page leave some text.

### Bibliographic citations

`[@key]` citations are resolved by `pandoc --citeproc` with the `bibliography` and `csl` keys of the note (here Chicago
author-date); at the end of each chapter its *References* appear, with the cited works only. A key missing from the
`.bib`, or a `,` before another `@key` (a `;` is needed), is reported in `anomalies.md`, without automatic corrections.

The CSL style is not part of the repository: keep it in the data folder (`styles/`). The author-date style of the Chicago
Manual of Style, 18th edition (the official one, from Zotero) works with **one change**: uncomment the `publisher-place`
line in the `source-publication-publisher-bib` macro, so monographs come out as `City: Publisher` (the 18th edition omits
it by default). No `———` for a repeated author. The city appears only if `location`/`address` is filled in the `.bib`.

## Folders of files (`source=<folder>`)

`source=<folder>` reads the files; an entry's ID is the file name without `.md` (if `id_field` is given, that field of
the front matter). It chooses which to include and in what order with `series_order`, `exclude_prefixes` and the
exceptions `first` / `exclude` / `include`; natural order of the IDs within each series. `page_break_per_item`, `columns`
and end-of-entry figures (`{group=end}`, always at the bottom of the entry) are volume settings.

**Link to an entry** from a Markdown chapter: `[F1-02](F1-02.md)` (syntax `[text](file.md)`; `[[F1-02]]` works too). It
reads "F1-02" and is clickable in the PDF, with no colour or underline (`links` in the style). It works only for entries
included in the volume: if the file does not exist or the series is excluded, the link is reported in `anomalies.md` as
"unresolved chapter link" and only the text remains.

## Style (yaml blocks of volume.md)

In the volume note, under a heading (e.g. `## Style`), one or more ` ```yaml ` blocks with the keys below; Obsidian
colours them and the headings can be collapsed. All blocks are merged, and whatever is missing uses the **defaults**
given (no key is required: a note without style produces a complete volume, in Libertinus Serif 11 pt, the free font
bundled with Typst). The layers, from the lowest: `volume.md` blocks → `--config file.yaml|json` (optional) →
`--set key=value` (e.g. `--set styles.normal.size=10.5`). The `- ...` items inside a block are not chapters. A YAML
error stops the build and gives the line. In the tables: **T** = Typst PDF only, **W** = Word only, otherwise it applies
to both.

### styles: paragraph styles

`styles.<name>` is a dictionary of these keys (missing ones fall back to the style indicated, then to the defaults):

| Key | Default | Meaning |
|---|---|---|
| `font` | `Libertinus Serif` | family (if not installed, Typst/Word substitute another) |
| `size` | `11` | size in pt |
| `bold`, `italic` | `false` | |
| `color` | `000000` | hexadecimal, without `#` (quoted in YAML: `'000000'`) |
| `line_height` | `size × 1.2` | line pitch in **pt**, identical in Word and Typst |
| `first_line_indent` | `0` | first-line indent, pt (negative = hanging) |
| `indent_left`, `indent_right` | `0` | side indents, pt |
| `space_before`, `space_after` | `0` | spacing above/below, pt |
| `align` | `left` | `left`, `center`, `right`, `justify` |
| `paragraph_gap` | `4` | `quote` only: space between the paragraphs of the quotation, pt |
| `keep_together_chars` | `700` | `quote` only (T): a quotation shorter than this many characters is not split across pages |

The styles used and their fallback (if undefined):

| Style | What for | Fallback |
|---|---|---|
| `h1` … `h5` | headings (h1 = chapter); a missing `hN` uses the nearest defined level above | `h1` |
| `normal` | text | defaults above |
| `caption` | captions of figures and tables | – |
| `quote` | `> text` quotations | `normal` |
| `list` | lists | `normal` |
| `footnote` | footnotes | `normal` |
| `bibliography` | entries of the reference list | `normal` |
| `chapter_author` | the authors' line under the chapter title | `normal` |
| `toc_author` | the authors' line in the table of contents (T) | `chapter_author` |
| `table_header`, `table_body` | header and cells of tables | – |
| `header_title`, `header_pagenum` | running head: title and page number | – |
| *any other name* | called with `::: {.name}` (see "Title page and colophon") | `normal` |

### page, header, chapter_opener, chapter_numbering

| Key | Default | Meaning |
|---|---|---|
| `page.size` | `A4` | `A4` or `Letter` |
| `page.margin_top_cm`, `page.margin_bottom_cm` | `2.5` | top and bottom margins |
| `page.margin_interior`, `page.margin_exterior` | `2.5` | **mirrored** margins (interior = binding side), cm; for non-mirrored margins `margin_left_cm` / `margin_right_cm` (default 2.5) |
| `page.page_numbers` | `true` | page number in the running head |
| `page.chapter_start` | `right` | T: `right` = every chapter starts on a right-hand page (a blank page without running head is inserted if needed); `any` = one after the other |
| `header.enabled` | `true` | running head: odd pages title (towards the inside) and number (towards the outside), even pages mirrored |
| `header.title` | – | fallback text when the chapter has neither `running_title` nor `title` |
| `header.left_pages` | `author` | text of even pages: `author` = the chapter's authors (otherwise the volume's), `title` = like odd pages |
| `header.start_page` | `1` | number of the first page after the title page |
| `header.skip_chapter_first_page` | `true` | no running head on the first page of each chapter and on divider pages |
| `header.rule.enabled` | `true` | rule under the running head |
| `header.rule.color` | `000000` | |
| `header.rule.size_eighths_pt` | `4` | thickness in eighths of a pt |
| `header.rule.space_pt` | `2` | space between text and rule |
| `chapter_opener.offset_pct` | `33` | the h1 title of a chapter starts at this percentage of the page height |
| `chapter_numbering` | `true` | prefixes headings with the chapter number taken from the id (`6.` for chapters, `6.1` for sub-chapters); a heading already numbered by hand is left alone; a non-numeric id (`{id=preface}`) or `numbered=false` excludes the chapter |

### table

| Key | Default | Meaning |
|---|---|---|
| `table.empty_cell` | `–` | text of empty cells (all tables of the volume) |
| `table.rule_pt` | `0.75` | thickness of the rules above and below the table |
| `table.header_rule_pt` | `0.5` | thickness of the rule under the header (which repeats on every page) |
| `table.space_after_pt` | `14` | space after the table |
| `table.classes.<name>` | – | `{.name}` classes: `col_ratios` (column weights), `markup` (default `true`; `false`: cells do not interpret `**`/`*`), `empty_cell`, `full_width` (T: never floating) |

Tables with more than 20 rows are always full width; shorter ones, in multi-column chapters, float at full width.

### images

| Key | Default | Meaning |
|---|---|---|
| `images.max_width_cm`, `images.max_height_cm` | `15`, `20` | ceilings on the size of a figure (overridden by the figure's `width`/`height`) |
| `images.figure_space_before_pt` | `4` | space above a figure |
| `images.figure_space_after_pt` | – | space below (without it: that of the `caption` style) |
| `images.min_caption_cm` | `5` | T: minimum caption width (otherwise it is as wide as the image) |
| `images.float_position` | `auto` | T, multi-column chapters: `auto`, `top`, `bottom` (position of floating figures) |
| `images.flow_max_height_cm` | = `max_height_cm` | T, multi-column chapters: ceiling on the height of floating figures, so that two figures on the same page leave some text |
| `images.wrap_width_cm` | `5` | T: width of a `position=left|right` figure without `width` |
| `images.wrap_gutter_pt` | `12` | T: distance between a figure and the text flowing around it |
| `images.figures_landscape_per_page` | – | W: how many landscape figures per page in figure sections (without it: maximum height `max_height_cm`) |
| `images.figures_row_reserve_cm` | `1.2` | W: space reserved per row in figure sections |
| `images.classes.<name>` | – | `{class=name}` classes: `width_pct` (of the usable width; free height; default 100), `space_before_pt`, `space_after_pt` (default as `figure_space_before_pt`) |

### typst, links, typography, annotations

| Key | Default | Meaning |
|---|---|---|
| `typst.column_gutter_cm` | `1.0` | distance between columns |
| `typst.flow_heading_min_level` | `3` | headings of this level and below, between two multi-column texts, stay in the column flow |
| `typst.balance_columns_max` | `0.5` | two-column texts shorter than this fraction of a page are balanced (0 = off) |
| `typst.balance_min_flow` | `0.2` | if they do not fit in the remaining space, they flow into the columns anyway if at least this fraction of a page is left; otherwise they go to the next page |
| `links.color` | `null` | colour of links between chapters (hexadecimal); `null` = like the text (for print) |
| `links.underline`, `links.bold` | `false` | |
| `typography.hyphenate` | `false` | `true`: automatic hyphenation |
| `typography.highlight_color` | `FFEB3B` | colour of `==highlight==` |
| `annotations.enabled` | `false` | like `--annotations` (Word comments / PDF annotations) |
| `annotations.author`, `annotations.initials` | `Author`, empty | author and initials of the comments |
| `annotations.color` | `FFD54F` | colour of annotations |
| `annotations.suggestions` | `accept` | without `--annotations`: `accept` = the new text of `{++ ++}`/`{~~ ~> ~~}` stays, `reject` = the old one |

### Complete example

```yaml
page: {size: A4, margin_top_cm: 3.5, margin_bottom_cm: 2.5, margin_interior: 4, margin_exterior: 3}
styles:
  h1: {font: Arno Pro, size: 20, align: center, line_height: 26, space_after: 20}
  normal: {font: Minion Pro, size: 11, line_height: 13, first_line_indent: 12, align: justify}
  caption: {font: Minion Pro, size: 9, italic: true, align: center}
table: {empty_cell: "–", classes: {finds: {col_ratios: [16, 14, 10, 9, 7, 7, 7, 9, 6], markup: false, full_width: true}}}
images: {max_width_cm: 14, classes: {plan: {width_pct: 100, space_before_pt: 20, space_after_pt: 16}}}
header: {title: My volume, left_pages: author, rule: {size_eighths_pt: 4}}
typography: {hyphenate: false}
```

### Font

Fonts are those installed on the computer (here: Arno Pro for headings, Minion Pro for text). If a font is missing, Typst
and Word substitute another.

## Differences between the two formats

The Typst PDF is the delivery format; the DOCX follows the same rules but has no columns, floating figures, text
flowing around figures, or `position`. Notes are real Word notes; the Word table of contents is a field to update (F9).

## License

MIT, see [LICENSE](LICENSE).
