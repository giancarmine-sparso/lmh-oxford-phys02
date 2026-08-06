"""Transverse-mass workflow preserving the original poster selection."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

import awkward as ak
import matplotlib.pyplot as plt
import numpy as np

from .plot_style import (
    ACCENT_ORANGE,
    PRIMARY_BLUE,
    paper_style,
    save_figure_variants,
)
from .selection import (
    DEFAULT_DATA_FILE,
    PROJECT_DIR,
    choose_tree,
    discover_root_files,
    first_item,
    open_root_file,
)


MT_BRANCHES = (
    "trigE",
    "lep_pt",
    "lep_eta",
    "lep_phi",
    "lep_type",
    "lep_isTightID",
    "lep_ptcone30",
    "met_et",
    "met_phi",
)
MT_BINS = np.linspace(0.0, 200.0, 51)
DEFAULT_OUTPUT_DIR = PROJECT_DIR / "plots" / "final"
POSTER_PANEL_TITLE_SIZE = 28
POSTER_PANEL_LABEL_SIZE = 26
POSTER_PANEL_TICK_SIZE = 23


@dataclass(frozen=True)
class MtConfig:
    input_path: Path = DEFAULT_DATA_FILE
    tree_name: str | None = "mini"
    step_size: str = "200 MB"
    output_dir: Path = DEFAULT_OUTPUT_DIR


@dataclass(frozen=True)
class MtChunk:
    broad_histogram: np.ndarray
    enriched_histogram: np.ndarray
    broad_events: int
    enriched_events: int


@dataclass(frozen=True)
class MtResult:
    bins: np.ndarray
    broad_histogram: np.ndarray
    enriched_histogram: np.ndarray
    broad_events: int
    enriched_events: int

    @property
    def selection_efficiency(self) -> float:
        return self.enriched_events / self.broad_events if self.broad_events else 0.0


def calculate_mt_chunk(arrays: Mapping[str, ak.Array]) -> MtChunk:
    """Calculate mT histograms for one chunk using the legacy selection."""

    lep_pt = first_item(arrays["lep_pt"]) / 1000.0
    lep_eta = first_item(arrays["lep_eta"])
    lep_phi = first_item(arrays["lep_phi"])
    lep_type = first_item(arrays["lep_type"])
    lep_is_tight = first_item(arrays["lep_isTightID"]) == 1
    lep_ptcone30 = first_item(arrays["lep_ptcone30"]) / 1000.0

    met_et = ak.to_numpy(arrays["met_et"]) / 1000.0
    met_phi = ak.to_numpy(arrays["met_phi"])
    trig_e = ak.to_numpy(arrays["trigE"])

    relative_isolation = np.divide(
        lep_ptcone30,
        lep_pt,
        out=np.full_like(lep_ptcone30, np.inf),
        where=lep_pt > 0,
    )
    delta_phi = np.arctan2(
        np.sin(lep_phi - met_phi),
        np.cos(lep_phi - met_phi),
    )
    mt_squared = 2.0 * lep_pt * met_et * (1.0 - np.cos(delta_phi))
    transverse_mass = np.sqrt(np.maximum(mt_squared, 0.0))
    abs_eta = np.abs(lep_eta)

    valid = (
        np.isfinite(lep_pt)
        & np.isfinite(lep_eta)
        & np.isfinite(met_et)
        & np.isfinite(transverse_mass)
    )
    broad_mask = valid & (lep_type == 11)
    outside_calorimeter_crack = (abs_eta < 1.37) | (abs_eta > 1.52)
    enriched_mask = (
        broad_mask
        & trig_e
        & (lep_pt >= 25.0)
        & (abs_eta < 2.47)
        & lep_is_tight
        & outside_calorimeter_crack
        & (relative_isolation < 0.10)
        & (met_et > 30.0)
    )

    return MtChunk(
        broad_histogram=np.histogram(transverse_mass[broad_mask], bins=MT_BINS)[0],
        enriched_histogram=np.histogram(
            transverse_mass[enriched_mask], bins=MT_BINS
        )[0],
        broad_events=int(np.count_nonzero(broad_mask)),
        enriched_events=int(np.count_nonzero(enriched_mask)),
    )


def accumulate_mt(config: MtConfig) -> MtResult:
    """Stream one or more ROOT files and accumulate both mT histograms."""

    root_files = discover_root_files(config.input_path, max_files=None)
    broad_histogram = np.zeros(len(MT_BINS) - 1, dtype=np.int64)
    enriched_histogram = np.zeros(len(MT_BINS) - 1, dtype=np.int64)
    broad_events = 0
    enriched_events = 0

    for file_path in root_files:
        with open_root_file(file_path) as root_file:
            tree_name = choose_tree(root_file, config.tree_name)
            tree = root_file[tree_name]
            missing = sorted(set(MT_BRANCHES) - set(tree.keys()))
            if missing:
                raise KeyError(
                    f"{file_path.name} is missing branches: " + ", ".join(missing)
                )

            for arrays in tree.iterate(
                expressions=list(MT_BRANCHES),
                step_size=config.step_size,
                library="ak",
            ):
                chunk = calculate_mt_chunk(arrays)
                broad_histogram += chunk.broad_histogram
                enriched_histogram += chunk.enriched_histogram
                broad_events += chunk.broad_events
                enriched_events += chunk.enriched_events

    return MtResult(
        bins=MT_BINS.copy(),
        broad_histogram=broad_histogram,
        enriched_histogram=enriched_histogram,
        broad_events=broad_events,
        enriched_events=enriched_events,
    )


def plot_mt(result: MtResult, output_dir: Path) -> tuple[Path, Path]:
    """Write the mT comparisons and poster panels as PNG and PDF."""

    if result.broad_histogram.sum() == 0 or result.enriched_histogram.sum() == 0:
        raise ValueError("Both mT selections must contain events before plotting.")

    output_dir.mkdir(parents=True, exist_ok=True)
    raw_output = output_dir / "mt_before_after.png"
    normalized_output = output_dir / "mt_normalized_comparison.png"
    broad_panel_output = output_dir / "mt_broad_sample.png"
    selected_panel_output = output_dir / "mt_selected_sample.png"

    broad_normalized = result.broad_histogram / result.broad_histogram.sum()
    enriched_normalized = result.enriched_histogram / result.enriched_histogram.sum()

    with paper_style():
        figure, axes = plt.subplots(
            1,
            2,
            figsize=(10.8, 3.6),
            sharex=True,
            sharey=True,
            constrained_layout=True,
        )
        axes[0].stairs(
            result.broad_histogram,
            result.bins,
            fill=True,
            color=PRIMARY_BLUE,
            alpha=0.75,
            linewidth=0.8,
        )
        axes[0].set_title("Broad electron sample", fontsize=18)
        axes[1].stairs(
            result.enriched_histogram,
            result.bins,
            fill=True,
            color=ACCENT_ORANGE,
            alpha=0.75,
            linewidth=0.8,
        )
        axes[1].set_title("Selected sample", fontsize=18)
        for axis in axes:
            axis.set_xlim(0, 150)
            axis.set_xticks(np.arange(0, 151, 25))
            axis.set_ylim(bottom=0)
            axis.tick_params(axis="both", which="major", labelsize=15)
            axis.minorticks_on()
            axis.grid(True, which="major", axis="y", alpha=0.22, linewidth=0.5)
            axis.grid(False, which="minor")
        figure.supxlabel(r"Transverse mass $m_T$ [GeV]", fontsize=17)
        figure.supylabel("Events / 4 GeV", fontsize=17)
        save_figure_variants(figure, raw_output)
        plt.close(figure)

        shared_y_max = 1.05 * float(
            max(result.broad_histogram.max(), result.enriched_histogram.max())
        )
        panel_specs = (
            (
                result.broad_histogram,
                "Broad electron sample",
                PRIMARY_BLUE,
                broad_panel_output,
            ),
            (
                result.enriched_histogram,
                "Selected sample",
                ACCENT_ORANGE,
                selected_panel_output,
            ),
        )
        for histogram, title, color, output_path in panel_specs:
            figure, axis = plt.subplots(
                figsize=(10.8, 4.5),
                constrained_layout=True,
            )
            axis.stairs(
                histogram,
                result.bins,
                fill=True,
                color=color,
                alpha=0.75,
                linewidth=0.8,
            )
            axis.set_title(title, fontsize=POSTER_PANEL_TITLE_SIZE)
            axis.set_xlim(0, 150)
            axis.set_xticks(np.arange(0, 151, 25))
            axis.set_ylim(0, shared_y_max)
            axis.set_xlabel(
                r"Transverse mass $m_T$ [GeV]",
                fontsize=POSTER_PANEL_LABEL_SIZE,
            )
            axis.set_ylabel("Events / 4 GeV", fontsize=POSTER_PANEL_LABEL_SIZE)
            axis.tick_params(
                axis="both",
                which="major",
                labelsize=POSTER_PANEL_TICK_SIZE,
            )
            axis.minorticks_on()
            axis.grid(True, which="major", axis="y", alpha=0.22, linewidth=0.5)
            axis.grid(False, which="minor")
            save_figure_variants(figure, output_path)
            plt.close(figure)

        figure, axis = plt.subplots(
            figsize=(6.4, 4.2),
            constrained_layout=True,
        )
        axis.stairs(
            broad_normalized,
            result.bins,
            label="Broad electron sample",
            color=PRIMARY_BLUE,
            linewidth=1.2,
        )
        axis.stairs(
            enriched_normalized,
            result.bins,
            label=r"$W\rightarrow e\nu$-enriched sample",
            color=ACCENT_ORANGE,
            linewidth=1.2,
        )
        axis.set(
            xlabel=r"Transverse mass $m_T$ [GeV]",
            ylabel="Fraction of events / 4 GeV",
            xlim=(0, 200),
            title=r"Shape comparison for $W\rightarrow e\nu$ candidates",
        )
        axis.set_ylim(bottom=0)
        axis.minorticks_on()
        axis.grid(True, which="major", axis="y", alpha=0.22, linewidth=0.5)
        axis.grid(False, which="minor")
        axis.legend(frameon=True, loc="best")
        save_figure_variants(figure, normalized_output)
        plt.close(figure)
    return raw_output, normalized_output


def run_mt(config: MtConfig) -> MtResult:
    result = accumulate_mt(config)
    print(f"Events in broad sample   : {result.broad_events:,}")
    print(f"Events in enriched sample: {result.enriched_events:,}")
    print(f"Selection efficiency     : {result.selection_efficiency:.2%}")
    raw_output, normalized_output = plot_mt(result, config.output_dir)
    print(f"Created: {raw_output}")
    print(f"Created: {raw_output.with_suffix('.pdf')}")
    for panel_name in ("mt_broad_sample", "mt_selected_sample"):
        panel_output = config.output_dir / f"{panel_name}.png"
        print(f"Created: {panel_output}")
        print(f"Created: {panel_output.with_suffix('.pdf')}")
    print(f"Created: {normalized_output}")
    print(f"Created: {normalized_output.with_suffix('.pdf')}")
    return result
