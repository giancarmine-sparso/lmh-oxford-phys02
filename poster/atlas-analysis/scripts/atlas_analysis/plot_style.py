"""Shared paper-grade styling and figure export helpers."""

from __future__ import annotations

from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path
import shutil
import subprocess
from typing import Iterator

import matplotlib.pyplot as plt
from matplotlib.figure import Figure
import scienceplots  # noqa: F401  -- register the ``science`` style


PRIMARY_BLUE = "#4878A6"
ACCENT_ORANGE = "#C44E2C"
NEUTRAL_DARK = "#222222"

_STIX_TWO_LATEX_PREAMBLE = (
    r"\usepackage[T1]{fontenc}"
    r"\usepackage[utf8]{inputenc}"
    r"\usepackage{stix2}"
)


@lru_cache(maxsize=1)
def latex_stix_two_available() -> bool:
    """Return whether Matplotlib can render STIX Two through LaTeX."""

    required_commands = ("latex", "dvipng", "kpsewhich")
    if any(shutil.which(command) is None for command in required_commands):
        return False

    completed = subprocess.run(
        ["kpsewhich", "stix2.sty"],
        check=False,
        capture_output=True,
        text=True,
    )
    return completed.returncode == 0 and bool(completed.stdout.strip())


@contextmanager
def paper_style(*, use_tex: bool | None = None) -> Iterator[None]:
    """Apply the shared SciencePlots/STIX Two style within a local context."""

    latex_enabled = latex_stix_two_available() if use_tex is None else use_tex
    parameters: dict[str, object] = {
        "figure.dpi": 200,
        "savefig.dpi": 600,
        "font.size": 11,
        "axes.titlesize": 12,
        "axes.labelsize": 11,
        "xtick.labelsize": 10,
        "ytick.labelsize": 10,
        "legend.fontsize": 10,
        "figure.titlesize": 13,
        "font.family": "serif",
        "text.usetex": latex_enabled,
    }
    if latex_enabled:
        parameters["text.latex.preamble"] = _STIX_TWO_LATEX_PREAMBLE
    else:
        parameters.update(
            {
                "font.serif": ["STIX Two Text"],
                "mathtext.fontset": "custom",
                "mathtext.rm": "STIX Two Text",
                "mathtext.it": "STIX Two Text:style=italic",
                "mathtext.bf": "STIX Two Text:weight=bold",
                "mathtext.bfit": "STIX Two Text:style=italic:weight=bold",
                "mathtext.cal": "STIX Two Math",
                "mathtext.sf": "STIX Two Text",
                "mathtext.tt": "STIX Two Text",
                "mathtext.fallback": "stix",
            }
        )

    with plt.style.context(["science"]), plt.rc_context(parameters):
        yield


def save_figure_variants(figure: Figure, output_path: str | Path) -> tuple[Path, Path]:
    """Save a requested figure plus same-stem PNG and PDF variants."""

    primary_output = Path(output_path)
    primary_output.parent.mkdir(parents=True, exist_ok=True)
    png_output = primary_output.with_suffix(".png")
    pdf_output = primary_output.with_suffix(".pdf")

    outputs = dict.fromkeys((primary_output, png_output, pdf_output))
    for output in outputs:
        save_options: dict[str, object] = {"bbox_inches": "tight"}
        if output.suffix.lower() != ".pdf":
            save_options["dpi"] = 600
        figure.savefig(output, **save_options)

    return png_output, pdf_output
