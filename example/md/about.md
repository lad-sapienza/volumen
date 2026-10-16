---
title: About this example
---
This folder is a complete, small volume you can typeset right away. The text is Samuel Butler's prose translation of
Homer's *Odyssey* (1900, public domain), taken from [Project Gutenberg](https://www.gutenberg.org/ebooks/1727); the first
three books are included.

Open `volume.md` to see how a volume is composed: a few lines of frontmatter, a list of links to the chapter files, and
a `yaml` block with the style. Everything else lives in the chapter files themselves.

| Book | Setting | Main characters |
|---|---|---|
| I | Olympus, then Ithaca | Minerva, Telemachus |
| II | Ithaca | Telemachus, the suitors |
| III | Pylos | Nestor, Telemachus |

Table: The books included in this example {#tab-books}

Change a value in the style block and build again: the title page, the table of contents, the running heads and the
numbering all follow[^1].

[^1]: The table above lists the books; each is a separate file. Links between chapters take the chapter number: see chapter [](book-1.md).
