# The Aharonov–Bohm effect

This directory contains the source of a twelve-minute talk prepared for LMH
Oxford PHYS02. The deck uses a short interactive simulation and an animation
to explain why electromagnetic potentials can have observable consequences in
quantum mechanics.

[Open the interactive talk](https://github.com/giancarmine-sparso/lmh-oxford-phys02/releases/latest/download/LMH-PHYS02-Aharonov-Bohm-talk.html)
or [download the PDF](https://github.com/giancarmine-sparso/lmh-oxford-phys02/releases/latest/download/LMH-PHYS02-Aharonov-Bohm-talk.pdf).

## Build the deck

The HTML deck requires [Quarto](https://quarto.org/) 1.10 or later:

```bash
cd talk
quarto preview index.qmd
```

Build the self-contained HTML with:

```bash
quarto render index.qmd
```

The result is written to `dist/index.html`. To export the thirteen-slide PDF,
install Chromium or Chrome, Node.js 22 or later, FFmpeg and `pdfinfo`, then run:

```bash
./scripts/export_pdf.sh
```

The export script renders the deck, replaces the video with its final teaching
frame for print and checks the resulting page count.

## Written notes and figures

The longer notes require LuaLaTeX and can be compiled separately:

```bash
cd talk/notes
latexmk -lualatex -interaction=nonstopmode -halt-on-error main.tex
```

Figure sources live in `figures-src/`, `manim/` and the Python directories
under `scripts/` and `notes/scripts/`. Their generated assets are kept only
when they are consumed by the deck or the notes.

Third-party image credits and licences are recorded in the repository
[notices](../THIRD_PARTY_NOTICES.md).
