#let text-w = 15.0cm
#let page-bottom = 2.5cm
#let chlink(anchor, body) = context {
  if query(label(anchor)).len() > 0 { link(label(anchor), body) } else { body }
}
#let balanced-cols(anchor, gutter, max-frac, min-frac, body) = context {
  let colw = (text-w - gutter) / 2
  let h = measure(width: colw, body).height
  let hb = h / 2 + 1.5 * text.size
  let found = query(label(anchor))
  let rem = if found.len() == 0 { none } else { page.height - page-bottom - found.first().location().position().y }
  if rem == none or hb > max-frac * page.height or (hb > rem and rem >= min-frac * page.height) {
    columns(2, gutter: gutter, body)
  } else { block(breakable: false, height: hb, columns(2, gutter: gutter, body)) }
}
#set page(width: 21.0cm, height: 29.7cm, margin: (inside: 3.5cm, outside: 2.5cm, top: 3cm, bottom: 2.5cm))
#set text(font: "Libertinus Serif", size: 11pt, top-edge: 0.75em, bottom-edge: -0.25em, fill: rgb("#000000"), hyphenate: false)
#set align(left)
#set par(justify: true, leading: 3pt, spacing: 3pt)
#set page(header: none)
#show footnote.entry: it => {
  set text(font: "Libertinus Serif", size: 11pt, weight: "regular", fill: rgb("#000000"))
  set par(justify: true, leading: 3pt, first-line-indent: 0pt, spacing: 3pt)
  it
}
#set footnote.entry(separator: line(length: 30%, stroke: 0.5pt), clearance: 6pt, gap: 2pt)



#import "@preview/wrap-it:0.1.1": wrap-content

#v(113.39pt)
#block(width: 100%)[#set text(font: "Libertinus Serif", size: 28.0pt, weight: "regular", style: "normal", fill: rgb("#000000"))
#set par(justify: false, leading: 5.6pt, spacing: 5.6pt, linebreaks: "optimized")
#align(center)[Volume di prova]]
#v(0pt)

#pagebreak()

#v(0pt)
#block(width: 100%)[#set text(font: "Libertinus Serif", size: 12.0pt, weight: "regular", style: "normal", fill: rgb("#000000"))
#set par(justify: false, leading: 2.4pt, spacing: 2.4pt, linebreaks: "optimized")
#align(left)[Colophon di prova]]
#v(0pt)

#pagebreak(weak: true, to: "odd")

#counter(page).update(1)
#set page(header: context {
  let pg = counter(page).get().first()
  let odd = calc.rem(pg, 2) == 1
  let starts = query(<chapter-start>)
  let here-page = here().page()
  let on-page = starts.filter(m => m.location().page() == here-page)
  let before = starts.filter(m => m.location().page() < here-page)
  let cur-start = if on-page.len() > 0 { on-page.first().value } else if before.len() > 0 { before.last().value } else { (title: "Volume di prova", left: none) }
  let cur = cur-start.title
  let cur-left = if cur-start.left != none { cur-start.left } else { cur }
  let title-style = it => text(font: "Libertinus Serif", size: 11pt, weight: "regular", style: "normal", it)
  let title-part = title-style[#cur]
  let left-part = title-style[#cur-left]
  let num-part = text(font: "Libertinus Serif", size: 11pt, weight: "regular")[#pg]
  let row = if odd [#title-part #h(1fr) #num-part] else [#num-part #h(1fr) #left-part]
  let ends = query(<chapter-end>).map(m => m.location().page())
  let start-pages = starts.map(m => m.location().page())
  let blank = ends.any(e => e < here-page and start-pages.filter(sp => sp > e).fold(1000000, calc.min) > here-page)
  let hide = (true and on-page.len() > 0) or blank
  block(width: 100%)[#if not hide [
    #row
    #v(2pt)
    #line(length: 100%, stroke: 0.5pt + rgb("#000000"))
  ]]
})


#metadata((title: "", left: "")) <chapter-start>

#v(0pt, weak: true)
#block(sticky: true, width: 100%)[#align(center)[#par(leading: 4.0pt, justify: false)[#text(font: "Libertinus Serif", size: 20pt, weight: "regular", hyphenate: false, fill: rgb("#000000"))[Contents]]]
#v(0pt)]

#show outline.entry: it => {
  let entry = link(it.element.location(), pad(left: (it.level - 1) * 1em, grid(
    columns: (1fr, auto), align: (left, right + bottom),
    [#it.body()#box(width: 1fr, layout(size => box(width: size.width + 1.5cm - 0.5em, it.fill)))],
    [#h(1.5cm)#it.page()])))
  entry
  let s = it.element.supplement
  if s != none and s != auto {
    pad(left: (it.level - 1) * 1em, text(font: "Libertinus Serif", size: 11pt, style: "normal", fill: rgb("#000000"), s))
    v(0pt)
  }
}

#outline(title: none, depth: 2, indent: 1em)
#metadata(none) <chapter-end>
#pagebreak(weak: true, to: "odd")

#metadata((title: "Prefazione", left: "Ada Autrice, Bruno Autore")) <chapter-start>

#v(33%)

#place(hide[#heading(level: 1, outlined: true, bookmarked: true, numbering: none, supplement: none)[Prefazione]<ch_preface>])
#v(0pt, weak: true)
#block(sticky: true, width: 100%)[#align(center)[#par(leading: 4.0pt, justify: false)[#text(font: "Libertinus Serif", size: 20pt, weight: "regular", hyphenate: false, fill: rgb("#000000"))[Prefazione]]]
#v(0pt)]

#[#set par(first-line-indent: (amount: 12pt, all: true))
Testo della prefazione con _corsivo_, *grassetto* e apice 18#super[th].]

#metadata(none) <chapter-end>
#pagebreak(weak: true, to: "odd")

#metadata((title: "1. Primo capitolo", left: "Ada Autrice")) <chapter-start>

#v(33%)

#place(hide[#heading(level: 1, outlined: true, bookmarked: true, numbering: none, supplement: [Ada Autrice])[1\. Primo capitolo]<ch_1>])
#v(0pt, weak: true)
#block(sticky: true, width: 100%)[#align(center)[#par(leading: 4.0pt, justify: false)[#text(font: "Libertinus Serif", size: 20pt, weight: "regular", hyphenate: false, fill: rgb("#000000"))[1\. Primo capitolo]]]
#v(0pt)]

#v(0pt)
#align(left)[#text(font: "Libertinus Serif", size: 11pt, fill: rgb("#000000"))[Ada Autrice]]
#v(12pt)

#[#set par(first-line-indent: (amount: 12pt, all: true))
Il sito fu abitato fin dal Bronzo (Rossi 2019, 49) e poi abbandonato#footnote[Nota con un link al #chlink("ch_2_1")[capitolo beta 2.1] dentro.]. Vedi anche la Fig. 1.1 e il #chlink("ch_2_1")[capitolo seguente 2.1].]

#place(hide[#heading(level: 2, outlined: true, bookmarked: true, numbering: none, supplement: none)[Sezione]])
#v(0pt, weak: true)
#block(sticky: true, width: 100%)[#align(center)[#par(leading: 4.0pt, justify: false)[#text(font: "Libertinus Serif", size: 20pt, weight: "regular", hyphenate: false, fill: rgb("#000000"))[Sezione]]]
#v(0pt)]

#v(0pt, weak: true)
#pad(left: 0pt, right: 0pt)[
#block(breakable: false)[#set text(font: "Libertinus Serif", size: 11pt, weight: "regular", style: "normal", fill: rgb("#000000"), top-edge: 0.75em, bottom-edge: -0.25em)
#set par(justify: true, leading: 3pt, spacing: 7pt, first-line-indent: 0pt)
#set text(costs: (widow: 1000%, orphan: 1000%))
Una citazione di prova. \
#h(1fr) — Fonte]]
#v(0pt, weak: true)

#v(0pt, weak: true)
#[#set text(font: "Libertinus Serif", size: 11pt, weight: "regular", style: "normal", fill: rgb("#000000"), top-edge: 0.75em, bottom-edge: -0.25em)
#set par(justify: true, leading: 3pt, spacing: 3pt, first-line-indent: 0pt)
#set list(indent: 30pt, body-indent: -12pt)
#set enum(indent: 30pt, body-indent: -12pt)
- primo
- secondo
  - annidato]
#v(0pt, weak: true)

#v(0pt, weak: true)
#[#set text(font: "Libertinus Serif", size: 11pt, weight: "regular", style: "normal", fill: rgb("#000000"), top-edge: 0.75em, bottom-edge: -0.25em)
#set par(justify: true, leading: 3pt, spacing: 3pt, first-line-indent: 0pt)
#set list(indent: 30pt, body-indent: -12pt)
#set enum(indent: 30pt, body-indent: -12pt)
+ uno
+ due]
#v(0pt, weak: true)

#v(4pt)
#align(center, block(breakable: false, width: 9.00cm)[
#place(hide(figure([], kind: "volumen-fig", supplement: none, outlined: true, caption: [Fig. 1.1. Pianta del sito])))
#align(center)[#image("@ROOT@/md/pic-a.png", width: 9.00cm)]
#align(left)[#text(font: "Libertinus Serif", size: 11pt, weight: "regular", fill: rgb("#000000"))[Fig. 1.1. Pianta del sito]]
])

#block(sticky: true, width: 100%)[#align(left)[#text(font: "Libertinus Serif", size: 11pt, fill: rgb("#000000"))[Table 1.1. Reperti per classe]]#v(0pt)]
#[#set par(justify: false)
#set text(hyphenate: false)
#table(
  columns: (7.3fr, 6fr),
  stroke: none,
  table.hline(stroke: 0.75pt),
  table.header(
    table.cell(align: left)[#text(font: "Libertinus Serif", size: 11pt, weight: "regular", fill: rgb("#000000"))[Classe]], table.cell(align: right)[#text(font: "Libertinus Serif", size: 11pt, weight: "regular", fill: rgb("#000000"))[N]],
  ),
  table.hline(stroke: 0.5pt),
  table.cell(align: left)[#text(font: "Libertinus Serif", size: 11pt, weight: "regular", fill: rgb("#000000"))[Ceramica]], table.cell(align: right)[#text(font: "Libertinus Serif", size: 11pt, weight: "regular", fill: rgb("#000000"))[12]],
  table.cell(align: left)[#text(font: "Libertinus Serif", size: 11pt, weight: "regular", fill: rgb("#000000"))[Vetro]], table.cell(align: right)[#text(font: "Libertinus Serif", size: 11pt, weight: "regular", fill: rgb("#000000"))[–]],
  table.hline(stroke: 0.75pt),
)
]

#v(14pt)

#place.flush()

#v(0pt, weak: true)
#block(sticky: true, width: 100%)[#align(center)[#par(leading: 4.0pt, justify: false)[#text(font: "Libertinus Serif", size: 20pt, weight: "regular", hyphenate: false, fill: rgb("#000000"))[References]]]
#v(0pt)]

#[#set text(font: "Libertinus Serif", size: 11pt, weight: "regular", style: "normal", fill: rgb("#000000"), top-edge: 0.75em, bottom-edge: -0.25em)
#set par(justify: true, leading: 3pt, spacing: 3pt, first-line-indent: 0pt)
#set par(hanging-indent: -12pt)
Rossi, Maria. 2019. _Il sito sulla collina_. Editore.
]

#metadata(none) <chapter-end>
#pagebreak(weak: true, to: "odd")

#metadata((title: "", left: none)) <chapter-start>

#place(hide(heading(level: 1, outlined: true, bookmarked: true, numbering: none, supplement: none)[2\. Parte seconda]))
#align(horizon + center)[#text(font: "Libertinus Serif", size: 20pt, weight: "bold", fill: rgb("#000000"))[2\. Parte seconda]]
#pagebreak()

#metadata(none) <chapter-end>
#pagebreak(weak: true, to: "odd")

#metadata((title: "Secondo", left: "Ada Autrice, Bruno Autore")) <chapter-start>

#place(hide[#heading(level: 2, outlined: true, bookmarked: true, numbering: none, supplement: none)[2\.1 Secondo capitolo]<ch_2_1>])
#v(0pt, weak: true)
#block(sticky: true, width: 100%)[#align(center)[#par(leading: 4.0pt, justify: false)[#text(font: "Libertinus Serif", size: 20pt, weight: "regular", hyphenate: false, fill: rgb("#000000"))[2\.1 Secondo capitolo]]]
#v(0pt)]

#columns(2, gutter: 1.0cm)[
#[#set par(first-line-indent: (amount: 12pt, all: true))
Un testo con passo evidenziato e #highlight(fill: rgb("#FFEB3B"))[evidenziato], nuovo e #strike[barrato]. Ritorna al #chlink("ch_1")[primo 1].]

#wrap-content(align: right, columns: (1fr, auto), column-gutter: 12pt, [#align(center, block(breakable: false, width: 5.00cm)[
#place(hide(figure([], kind: "volumen-fig", supplement: none, outlined: true, caption: [Fig. 2.1.1. Figura a destra])))
#align(center)[#image("@ROOT@/md/pic-b.png", width: 2.10cm)]
#align(left)[#text(font: "Libertinus Serif", size: 11pt, weight: "regular", fill: rgb("#000000"))[Fig. 2.1.1. Figura a destra]]
])], [#h(12pt)Paragrafo uno che scorre intorno alla figura.

#h(12pt)Paragrafo due.])
#place.flush()
]

#metadata(none) <chapter-end>
#pagebreak(weak: true, to: "odd")

#metadata((title: "2.2 Schede di prova", left: "Ada Autrice, Bruno Autore")) <chapter-start>

#place(hide[#heading(level: 2, outlined: true, bookmarked: true, numbering: none, supplement: none)[2\.2 Schede di prova]<ch_2_2>])
#v(0pt, weak: true)
#block(sticky: true, width: 100%)[#align(center)[#par(leading: 4.0pt, justify: false)[#text(font: "Libertinus Serif", size: 20pt, weight: "regular", hyphenate: false, fill: rgb("#000000"))[2\.2 Schede di prova]]]
#v(0pt)]

#place(hide[#heading(level: 3, outlined: true, bookmarked: true, numbering: none, supplement: none)[B-1]<ch_B_1>])
#v(0pt, weak: true)
#block(sticky: true, width: 100%)[#align(center)[#par(leading: 4.0pt, justify: false)[#text(font: "Libertinus Serif", size: 20pt, weight: "regular", hyphenate: false, fill: rgb("#000000"))[B-1]]]
#v(0pt)]

#[#set par(first-line-indent: (amount: 12pt, all: true))
Scheda B uno.]

#pagebreak()
#place(hide[#heading(level: 3, outlined: true, bookmarked: true, numbering: none, supplement: none)[A-1]<ch_A_1>])
#v(0pt, weak: true)
#block(sticky: true, width: 100%)[#align(center)[#par(leading: 4.0pt, justify: false)[#text(font: "Libertinus Serif", size: 20pt, weight: "regular", hyphenate: false, fill: rgb("#000000"))[A-1]]]
#v(0pt)]

#[#set par(first-line-indent: (amount: 12pt, all: true))
Scheda A uno.]

#v(10pt)
#align(center, block(breakable: false, width: 12.00cm)[
#place(hide(figure([], kind: "volumen-fig", supplement: none, outlined: true, caption: [Fig. 2.2.1. Pianta A])))
#align(center)[#image("@ROOT@/md/cards/A-1-plan.png", width: 12.00cm)]
#align(left)[#text(font: "Libertinus Serif", size: 11pt, weight: "regular", fill: rgb("#000000"))[Fig. 2.2.1. Pianta A]]
])
#v(8pt)

#[#set par(justify: false)
#set text(hyphenate: false)
#table(
  columns: (3fr, 1fr),
  stroke: none,
  table.hline(stroke: 0.75pt),
  table.header(
    table.cell(align: left)[#text(font: "Libertinus Serif", size: 11pt, weight: "regular", fill: rgb("#000000"))[Classe]], table.cell(align: left)[#text(font: "Libertinus Serif", size: 11pt, weight: "regular", fill: rgb("#000000"))[N]],
  ),
  table.hline(stroke: 0.5pt),
  table.cell(align: left)[#text(font: "Libertinus Serif", size: 11pt, weight: "regular", fill: rgb("#000000"))[Ceramica]], table.cell(align: left)[#text(font: "Libertinus Serif", size: 11pt, weight: "regular", fill: rgb("#000000"))[3]],
  table.cell(align: left)[#text(font: "Libertinus Serif", size: 11pt, weight: "regular", fill: rgb("#000000"))[Vetro]], table.cell(align: left)[#text(font: "Libertinus Serif", size: 11pt, weight: "regular", fill: rgb("#000000"))[–]],
  table.hline(stroke: 0.75pt),
)
]

#v(14pt)

#v(4pt)
#align(center, block(breakable: false, width: 15.00cm)[
#place(hide(figure([], kind: "volumen-fig", supplement: none, outlined: true, caption: [Fig. 2.2.2. Fine scheda])))
#align(center)[#image("@ROOT@/md/cards/A-1-end.png", width: 15.00cm)]
#align(left)[#text(font: "Libertinus Serif", size: 11pt, weight: "regular", fill: rgb("#000000"))[Fig. 2.2.2. Fine scheda]]
])

#pagebreak()
#place(hide[#heading(level: 3, outlined: true, bookmarked: true, numbering: none, supplement: none)[A-2]<ch_A_2>])
#v(0pt, weak: true)
#block(sticky: true, width: 100%)[#align(center)[#par(leading: 4.0pt, justify: false)[#text(font: "Libertinus Serif", size: 20pt, weight: "regular", hyphenate: false, fill: rgb("#000000"))[A-2]]]
#v(0pt)]

#[#set par(first-line-indent: (amount: 12pt, all: true))
Scheda A due.]

#metadata(none) <chapter-end>
#pagebreak(weak: true, to: "odd")

#metadata((title: "Conclusioni", left: "Ada Autrice, Bruno Autore")) <chapter-start>

#v(33%)

#place(hide[#heading(level: 1, outlined: true, bookmarked: true, numbering: none, supplement: none)[Conclusioni]<ch_3>])
#v(0pt, weak: true)
#block(sticky: true, width: 100%)[#align(center)[#par(leading: 4.0pt, justify: false)[#text(font: "Libertinus Serif", size: 20pt, weight: "regular", hyphenate: false, fill: rgb("#000000"))[Conclusioni]]]
#v(0pt)]

#[#set par(first-line-indent: (amount: 12pt, all: true))
Fine del volume.]

#metadata(none) <chapter-end>
#pagebreak(weak: true, to: "odd")

#metadata((title: "", left: "")) <chapter-start>
#v(0pt, weak: true)
#block(sticky: true, width: 100%)[#align(center)[#par(leading: 4.0pt, justify: false)[#text(font: "Libertinus Serif", size: 20pt, weight: "regular", hyphenate: false, fill: rgb("#000000"))[List of Figures]]]
#v(0pt)]
#[
#show outline.entry: it => link(it.element.location(), block(width: 100%, spacing: 0.45em)[#it.body()#[: ]#it.page()])
#set text(font: "Libertinus Serif", size: 8pt)
#set par(justify: false, leading: 2.4pt, hanging-indent: 1.2em)
#columns(2, gutter: 0.8cm)[
#outline(title: none, target: figure.where(kind: "volumen-fig"), indent: 0em)
]
]