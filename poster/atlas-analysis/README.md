# ATLAS Open Data analysis

This project contains the event selection, transverse-mass plots and
data-driven ABCD estimate used in the poster. Shared analysis code lives under
`scripts/atlas_analysis/`; the three Python files directly under `scripts/`
are the supported command-line entry points.

## Setup

The environment requires Python 3.14 or later and
[uv](https://docs.astral.sh/uv/):

```bash
cd poster/atlas-analysis
uv sync
```

The analysis uses `data_A.1lep.root` from the
[ATLAS 13 TeV one-lepton collection](https://opendata.cern.ch/record/15001),
DOI [10.7483/OPENDATA.ATLAS.NQ31.Y1OO](https://doi.org/10.7483/OPENDATA.ATLAS.NQ31.Y1OO).
Download that file from the record and place it at:

```text
data/1lep/Data/data_A.1lep.root
```

The dataset is intentionally not stored in Git.

## Run the analysis

```bash
uv run python scripts/inspect_sample.py
uv run python scripts/plot_mt.py
uv run python scripts/run_abcd.py
```

Each command supports `--help` and accepts an alternative input path. The
output directory, tree name and chunk size can also be changed where relevant.

The transverse-mass and ABCD workflows retain different selections because
they answer different questions:

| Workflow | Candidate and common selection |
| --- | --- |
| Transverse mass | First reconstructed lepton; electron trigger; $p_T \geq 25$ GeV; tight ID; relative isolation below 0.10; $E_T^\text{miss} > 30$ GeV |
| ABCD | Highest-$p_T$ electron; $p_T \geq 30$ GeV; tight-ID baseline; isolation and $E_T^\text{miss}$ remain uncut until region assignment |

The ABCD regions use isolation below 0.10 or at least 0.20, and $E_T^\text{miss}$ at most
25 GeV or at least 30 GeV. Events in the gaps are excluded.

## Published outputs

- [ABCD plane](plots/final/abcd_plane_data.png) and its
  [numerical summary](plots/final/abcd_plane_data.txt)
- [Transverse mass before and after selection](plots/final/mt_before_after.png)
- [Broad selected sample](plots/final/mt_broad_sample.png)
- [Final selected sample](plots/final/mt_selected_sample.png)
- [Normalised comparison](plots/final/mt_normalized_comparison.png)

Matching PDF figures are kept for the poster build.
