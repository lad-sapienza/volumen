---
type: volume
title: The Odyssey
subtitle: Translated by Samuel Butler (1900)
authors: ["Homer"]
lang: en-GB
toc: true
toc_depth: 1
output_name: odyssey
frontmatter: ["[title-page](title-page.md)"]
---

An example volume. This free text is ignored; only the list below composes the book.

- [about](about.md) {id=about}
- Books {divider}
  - [book-1](book-1.md)
  - [book-2](book-2.md)
  - [book-3](book-3.md)

## Style

```yaml
page: {size: A5, margin_top_cm: 2.2, margin_bottom_cm: 2, margin_interior: 2.2, margin_exterior: 1.8}
styles:
  normal: {size: 10.5, line_height: 13.5, first_line_indent: 12, align: justify}
  h1: {size: 18, align: center, space_after: 16}
header: {title: The Odyssey}
```
