# Finding the W in the Noise

This directory contains the A1 poster prepared for LMH Oxford PHYS02 and the
analysis used to produce its plots. The poster follows reconstructed
$W \to e\nu$ candidates from event selection and transverse mass to a
data-driven ABCD background estimate.

[Download the final poster](https://github.com/giancarmine-sparso/lmh-oxford-phys02/releases/download/v1.0.0/LMH-PHYS02-Finding-the-W-in-the-Noise-poster.pdf).

## Build the poster

The poster requires LuaLaTeX, `latexmk`, `beamerposter`, STIX Two Text and STIX
Two Math. Build it from the graphics directory:

```bash
cd poster/graphics
latexmk -lualatex -interaction=nonstopmode -halt-on-error -outdir=build poster.tex
```

The generated PDF is written to `graphics/build/poster.pdf`. From the
repository root, `./scripts/build_release.sh` also packages it under the
stable release filename.

## Supporting work

- [ATLAS Open Data analysis](atlas-analysis/) contains the Python selection,
  transverse-mass and ABCD workflows.
- [Toy Monte Carlo](monte-carlo-simulation/) illustrates the idealised
  Jacobian endpoint with a Rust generator and a Python plotting step.
- `graphics/poster.tex` is the poster source; all referenced plots and visual
  assets are versioned beside the analysis.

## Scientific scope

The ABCD calculation is a preliminary, data-only estimate made from one
educational ATLAS sample. It is not a precision background model or a
measurement of the $W$-boson yield. The toy Monte Carlo is generator-level and
does not include detector response, backgrounds or transverse $W$ recoil.

ATLAS media, institutional marks and dataset provenance are documented in the
repository [third-party notices](../THIRD_PARTY_NOTICES.md).
