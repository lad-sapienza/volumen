---
type: volume
title: Volume di prova
authors: ["Ada Autrice | Università di Prova", "Bruno Autore"]
lang: it-IT
toc: true
toc_depth: 2
list_of_figures: true
output_name: mini
images_dir: img
bibliography: ../bib/refs.bib
frontmatter: ["[front](front.md)"]
---

Questa nota descrive il volume di prova; il testo libero e i titoli non contano.

- [preface](preface.md) {id=preface}
- [alfa](alfa.md)
- Parte seconda {divider}
  - [beta](beta.md) {columns=2}
  - Schede di prova {source=cards series_order=A,B exclude_prefixes=Z first=B-1 page_break_per_item}
- [gamma](gamma.md) {bibliography=false numbered=false}

## Stile

```yaml
page: {size: A4, margin_top_cm: 3, margin_bottom_cm: 2.5, margin_interior: 3.5, margin_exterior: 2.5}
styles:
  normal: {font: Libertinus Serif, size: 11, line_height: 14, first_line_indent: 12, align: justify}
  h1: {font: Libertinus Serif, size: 20, align: center}
table: {classes: {finds: {col_ratios: [3, 1], markup: false, full_width: true}}}
images: {classes: {plan: {width_pct: 80, space_before_pt: 10, space_after_pt: 8}}}
header: {title: Volume di prova}
```
