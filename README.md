# LMH Oxford PHYS02 — talk, poster and supporting analysis

This repository brings together two physics communication projects developed
for the LMH Oxford Summer Programme 2026: an interactive talk on the
Aharonov–Bohm effect and an A1 poster on recovering the $W \to e\nu$ signature
from ATLAS Open Data. The presentation sources are accompanied by the analysis
and small simulations used to build the final visuals.

## Projects

### Aharonov–Bohm talk

[![Title slide from the Aharonov–Bohm talk][talk-preview]](talk/)

A twelve-minute Quarto and Reveal.js presentation that moves from classical
fields to gauge freedom, quantum phase and the Tonomura experiment.
[Source](talk/)

### ATLAS Open Data poster

[![Finding the W in the Noise poster][poster-preview]](poster/)

A data-driven study of $W \to e\nu$ candidates using transverse mass and an
ABCD background estimate. [Source](poster/)

## Reproduce the release

The three release artefacts can be rebuilt from the repository root:

```bash
./scripts/build_release.sh
```

The script writes to the ignored `release/` directory. See the
[talk](talk/README.md) and [poster](poster/README.md) guides for the required
tools and the individual build commands.

## Repository layout

```text
talk/                         Quarto deck, written notes and visual sources
poster/graphics/              LuaLaTeX poster
poster/atlas-analysis/        Python analysis of the ATLAS data sample
poster/monte-carlo-simulation/  Rust toy generator and Python plotting step
references/                   Bibliography used by the talk
```

## Scientific scope

The poster uses the educational 2020 ATLAS Open Data release. Its ABCD result
is a preliminary, data-only background estimate, not a measurement of the
$W$-boson yield. The toy Monte Carlo fixes $m_W = 80.4$ GeV as an input and
does not model detector response or backgrounds.

This is an independent student project. It is not an official publication of,
or an endorsement by, ATLAS, CERN, the University of Oxford or Lady Margaret
Hall.

## Licences and credits

Source code is available under the [MIT License](LICENSE). Original prose,
slides, poster design and figures are available under
[CC BY 4.0](LICENSE-CONTENT.md). Logos, photographs, ATLAS material and other
external assets retain their original terms; see
[Third-party notices](THIRD_PARTY_NOTICES.md).

[talk-preview]: assets/previews/talk.png
[poster-preview]: assets/previews/poster.png
