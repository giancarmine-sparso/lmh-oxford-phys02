"""ABCD background estimate and its ATLAS Open Data workflow."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping

import awkward as ak
import matplotlib.pyplot as plt
from matplotlib.colors import Colormap, LogNorm
from matplotlib.offsetbox import AnnotationBbox, TextArea, VPacker
from matplotlib.ticker import LogFormatterMathtext, LogLocator, MaxNLocator
import numpy as np
import numpy.typing as npt

from .plot_style import NEUTRAL_DARK, paper_style, save_figure_variants
from .selection import (
    AnalysisSummary,
    BranchMap,
    CALORIMETER_TRANSITION_ABS_ETA_MAX,
    CALORIMETER_TRANSITION_ABS_ETA_MIN,
    DEFAULT_DATA_DIR,
    DEFAULT_ELECTRON_PT_MIN_GEV,
    DEFAULT_TRACK_ISOLATION_MAX,
    ELECTRON_ABS_ETA_MAX,
    MEV_TO_GEV,
    PROJECT_DIR,
    SelectedElectron,
    discover_root_files,
    inspect_file,
    print_electron_pt_summary,
    print_lepton_type_summary,
    print_track_isolation_summary,
    process_files,
    tight_id_selection_name,
)


FloatArray = npt.NDArray[np.float64]
BoolArray = npt.NDArray[np.bool_]

DEFAULT_ABCD_ISO_SIGNAL_MAX = 0.10
DEFAULT_ABCD_ISO_CONTROL_MIN = 0.20
DEFAULT_ABCD_MET_CONTROL_MAX_GEV = 25.0
DEFAULT_ABCD_MET_SIGNAL_MIN_GEV = 30.0
DEFAULT_ABCD_PLOT_PATH = PROJECT_DIR / "plots" / "final" / "abcd_plane_data.png"

# The ABCD plane is reproduced at roughly 1.4x its native width on the A1
# poster.  Scale every plot label together so their visual hierarchy remains
# stable while tuning them for the final printed size.
ABCD_POSTER_LABEL_SCALE = 1.60


@dataclass(frozen=True)
class ABCDAnalysisConfig:
    """Runtime configuration for the data-driven ABCD workflow."""

    input_path: Path = DEFAULT_DATA_DIR
    tree_name: str | None = None
    max_files: int | None = 1
    step_size: str = "100 MB"
    electron_pt_min_gev: float = DEFAULT_ELECTRON_PT_MIN_GEV
    track_isolation_max: float = DEFAULT_TRACK_ISOLATION_MAX
    met_branch: str = "met_et"
    abcd_iso_signal_max: float = DEFAULT_ABCD_ISO_SIGNAL_MAX
    abcd_iso_control_min: float = DEFAULT_ABCD_ISO_CONTROL_MIN
    abcd_met_control_max_gev: float = DEFAULT_ABCD_MET_CONTROL_MAX_GEV
    abcd_met_signal_min_gev: float = DEFAULT_ABCD_MET_SIGNAL_MIN_GEV
    abcd_plot_path: Path = DEFAULT_ABCD_PLOT_PATH


@dataclass(frozen=True)
class ABCDBoundaries:
    """Boundaries separating the signal and control regions."""

    iso_signal_max: float
    iso_control_min: float
    x_control_max: float
    x_signal_min: float

    def __post_init__(self) -> None:
        if self.iso_control_min < self.iso_signal_max:
            raise ValueError(
                "iso_control_min must be greater than or equal to iso_signal_max."
            )
        if self.x_signal_min < self.x_control_max:
            raise ValueError(
                "x_signal_min must be greater than or equal to x_control_max."
            )


@dataclass(frozen=True)
class RegionYield:
    """Yield and statistical variance for one ABCD region."""

    value: float
    variance: float
    n_events: int

    @property
    def uncertainty(self) -> float:
        return float(np.sqrt(self.variance))


@dataclass(frozen=True)
class ABCDResult:
    """ABCD region yields and the predicted background in region A."""

    regions: Mapping[str, RegionYield]
    predicted_a: float
    predicted_a_uncertainty: float

    @property
    def observed_a(self) -> float:
        return self.regions["A"].value


def _as_1d_float_array(values: npt.ArrayLike, name: str) -> FloatArray:
    array = np.asarray(values, dtype=np.float64)
    if array.ndim != 1:
        raise ValueError(f"{name} must be a one-dimensional array.")
    return array


def build_region_masks(
    isolation: npt.ArrayLike,
    discriminant: npt.ArrayLike,
    boundaries: ABCDBoundaries,
) -> dict[str, BoolArray]:
    """Return boolean masks for regions A, B, C, and D."""

    isolation_array = _as_1d_float_array(isolation, "isolation")
    discriminant_array = _as_1d_float_array(discriminant, "discriminant")
    if isolation_array.shape != discriminant_array.shape:
        raise ValueError("isolation and discriminant must have the same length.")

    finite = np.isfinite(isolation_array) & np.isfinite(discriminant_array)
    isolated = isolation_array < boundaries.iso_signal_max
    non_isolated = isolation_array >= boundaries.iso_control_min
    low = discriminant_array <= boundaries.x_control_max
    high = discriminant_array >= boundaries.x_signal_min

    return {
        "A": finite & isolated & high,
        "B": finite & non_isolated & high,
        "C": finite & isolated & low,
        "D": finite & non_isolated & low,
    }


def _weighted_region_yield(mask: BoolArray, weights: FloatArray) -> RegionYield:
    selected_weights = weights[mask]
    return RegionYield(
        value=float(np.sum(selected_weights)),
        variance=float(np.sum(selected_weights**2)),
        n_events=int(np.count_nonzero(mask)),
    )


def estimate_abcd(
    isolation: npt.ArrayLike,
    discriminant: npt.ArrayLike,
    boundaries: ABCDBoundaries,
    *,
    weights: npt.ArrayLike | None = None,
) -> ABCDResult:
    """Count the four regions and predict A as ``B * C / D``."""

    masks = build_region_masks(isolation, discriminant, boundaries)
    n_entries = len(next(iter(masks.values())))
    if weights is None:
        weights_array = np.ones(n_entries, dtype=np.float64)
    else:
        weights_array = _as_1d_float_array(weights, "weights")
        if len(weights_array) != n_entries:
            raise ValueError(
                "weights must have the same length as isolation and discriminant."
            )
        if not np.all(np.isfinite(weights_array)):
            raise ValueError("weights contains non-finite values.")

    regions = {
        name: _weighted_region_yield(mask, weights_array)
        for name, mask in masks.items()
    }
    b = regions["B"]
    c = regions["C"]
    d = regions["D"]
    if d.value <= 0:
        raise ZeroDivisionError(
            "Region D has a non-positive yield, so B*C/D is undefined."
        )

    predicted_a = b.value * c.value / d.value
    variance_a = (
        (c.value / d.value) ** 2 * b.variance
        + (b.value / d.value) ** 2 * c.variance
        + (b.value * c.value / d.value**2) ** 2 * d.variance
    )
    return ABCDResult(
        regions=regions,
        predicted_a=float(predicted_a),
        predicted_a_uncertainty=float(np.sqrt(variance_a)),
    )


def format_result(result: ABCDResult) -> str:
    lines = ["ABCD region yields:"]
    for name in ("A", "B", "C", "D"):
        region = result.regions[name]
        lines.append(
            f"  {name}: {region.value:.3f} ± {region.uncertainty:.3f} "
            f"({region.n_events} events)"
        )
    lines.append(
        "Predicted background in A: "
        f"{result.predicted_a:.3f} ± {result.predicted_a_uncertainty:.3f}"
    )
    return "\n".join(lines)


def summarize_region_assignment(
    isolation: npt.ArrayLike,
    discriminant: npt.ArrayLike,
    boundaries: ABCDBoundaries,
) -> str:
    """Return event counts in A/B/C/D and in the excluded gaps."""

    isolation_array = _as_1d_float_array(isolation, "isolation")
    discriminant_array = _as_1d_float_array(discriminant, "discriminant")
    if isolation_array.shape != discriminant_array.shape:
        raise ValueError("isolation and discriminant must have the same length.")

    finite = np.isfinite(isolation_array) & np.isfinite(discriminant_array)
    masks = build_region_masks(isolation_array, discriminant_array, boundaries)
    counts = {name: int(np.count_nonzero(mask)) for name, mask in masks.items()}
    assigned = np.logical_or.reduce(tuple(masks.values()))
    n_finite = int(np.count_nonzero(finite))
    n_excluded = int(np.count_nonzero(finite & ~assigned))
    n_invalid = int(len(finite) - n_finite)

    lines = [
        "ABCD assignment diagnostic:",
        *(f"  {name}: {counts[name]} events" for name in ("A", "B", "C", "D")),
        f"  excluded by gap: {n_excluded} events",
        f"  invalid/non-finite: {n_invalid} events",
        f"  finite input events: {n_finite}",
    ]
    if n_finite > 0:
        lines.append(f"  gap fraction: {100.0 * n_excluded / n_finite:.2f}%")
    return "\n".join(lines)


def _histogram2d_for_display(
    discriminant: FloatArray,
    isolation: FloatArray,
    *,
    bins: tuple[int, int],
    x_range: tuple[float, float],
    isolation_range: tuple[float, float],
    weights: FloatArray | None,
) -> tuple[FloatArray, FloatArray, FloatArray]:
    """Build the display histogram with upper overflow folded into edge bins."""

    x_low, x_high = x_range
    isolation_low, isolation_high = isolation_range
    display_discriminant = np.minimum(
        discriminant, np.nextafter(x_high, x_low)
    )
    display_isolation = np.minimum(
        isolation, np.nextafter(isolation_high, isolation_low)
    )
    return np.histogram2d(
        display_discriminant,
        display_isolation,
        bins=bins,
        range=(x_range, isolation_range),
        weights=weights,
    )


def _prepare_heatmap(
    histogram: FloatArray, *, logarithmic: bool
) -> tuple[
    FloatArray | np.ma.MaskedArray,
    Colormap,
    LogNorm | None,
    tuple[float, ...],
]:
    """Return a magma heatmap with non-positive log bins rendered dark."""

    base_cmap = plt.get_cmap("magma").copy()
    dark_color = base_cmap(0.0)
    cmap = base_cmap.with_extremes(bad=dark_color, under=dark_color)

    if not logarithmic:
        return histogram, cmap, None, dark_color

    histogram_for_plot = np.ma.masked_less_equal(histogram, 0.0, copy=False)
    positive_bins = histogram[histogram > 0.0]
    norm = None
    if positive_bins.size > 0:
        vmin = max(float(np.min(positive_bins)), 1e-12)
        vmax = float(np.max(positive_bins))
        if vmax <= vmin:
            vmax = float(np.nextafter(vmin, np.inf))
        norm = LogNorm(vmin=vmin, vmax=vmax)

    return histogram_for_plot, cmap, norm, dark_color


def _format_compact_count(count: int) -> str:
    """Format an event count compactly with three significant figures."""

    if count >= 1_000_000:
        return f"{count / 1_000_000:.3g}M"
    if count >= 1_000:
        return f"{count / 1_000:.3g}k"
    return f"{count:,}"


def _add_region_label(
    axis: plt.Axes,
    position: tuple[float, float],
    name: str,
    count: int,
    *,
    label_scale: float,
) -> None:
    """Add a compact two-level label at the visual centre of a region."""

    letter = TextArea(
        name,
        textprops={
            "fontsize": 15 * label_scale,
            "fontweight": "bold",
            "ha": "center",
            "color": NEUTRAL_DARK,
        },
    )
    count_text = TextArea(
        _format_compact_count(count),
        textprops={
            "fontsize": 10 * label_scale,
            "ha": "center",
            "color": NEUTRAL_DARK,
        },
    )
    contents = VPacker(children=[letter, count_text], align="center", pad=0, sep=1)
    label = AnnotationBbox(
        contents,
        position,
        xycoords="data",
        box_alignment=(0.5, 0.5),
        frameon=True,
        pad=0.2,
        bboxprops={
            "boxstyle": "round,pad=0.24,rounding_size=0.16",
            "facecolor": "white",
            "edgecolor": NEUTRAL_DARK,
            "linewidth": 0.75,
            "alpha": 0.82,
        },
        zorder=6,
    )
    axis.add_artist(label)


def plot_abcd_plane(
    isolation: npt.ArrayLike,
    discriminant: npt.ArrayLike,
    boundaries: ABCDBoundaries,
    output_path: str | Path,
    *,
    weights: npt.ArrayLike | None = None,
    x_range: tuple[float, float] = (0.0, 100.0),
    isolation_range: tuple[float, float] = (0.0, 0.50),
    bins: tuple[int, int] = (50, 50),
    x_label: str = r"$E_T^{\mathrm{miss}}$ [GeV]",
    isolation_label: str = "Relative electron isolation",
    title: str = "ABCD control regions",
    subtitle: str = "Preliminary data-only background study",
    logarithmic: bool = True,
) -> Path:
    """Plot the isolation-discriminant plane as matching PNG and PDF files.

    Upper overflow is folded into the visible edge bins for this display only.
    Region assignments and yields continue to use the original input arrays.
    """

    isolation_array = _as_1d_float_array(isolation, "isolation")
    discriminant_array = _as_1d_float_array(discriminant, "discriminant")
    if isolation_array.shape != discriminant_array.shape:
        raise ValueError("isolation and discriminant must have the same length.")

    finite = np.isfinite(isolation_array) & np.isfinite(discriminant_array)
    isolation_array = isolation_array[finite]
    discriminant_array = discriminant_array[finite]

    weights_array: FloatArray | None
    if weights is None:
        weights_array = None
    else:
        raw_weights = _as_1d_float_array(weights, "weights")
        if raw_weights.shape != finite.shape:
            raise ValueError("weights must have the same length as the input arrays.")
        if not np.all(np.isfinite(raw_weights)):
            raise ValueError("weights contains non-finite values.")
        weights_array = raw_weights[finite]

    if len(isolation_array) == 0:
        raise ValueError("No finite events are available for the ABCD plot.")

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    histogram, x_edges, y_edges = _histogram2d_for_display(
        discriminant_array,
        isolation_array,
        bins=bins,
        x_range=x_range,
        isolation_range=isolation_range,
        weights=weights_array,
    )
    histogram_for_plot, cmap, norm, dark_color = _prepare_heatmap(
        histogram, logarithmic=logarithmic
    )

    masks = build_region_masks(isolation, discriminant, boundaries)
    counts = {name: int(np.count_nonzero(mask)) for name, mask in masks.items()}
    x_low, x_high = x_range
    y_low, y_high = isolation_range
    low_x = 0.5 * (x_low + min(boundaries.x_control_max, x_high))
    high_x = 0.5 * (max(boundaries.x_signal_min, x_low) + x_high)
    isolated_y = 0.5 * (y_low + min(boundaries.iso_signal_max, y_high))
    nonisolated_y = 0.5 * (
        max(boundaries.iso_control_min, y_low) + y_high
    )

    with paper_style():
        figure, axis = plt.subplots(
            figsize=(7.2, 5.6),
            constrained_layout=True,
            facecolor="white",
        )
        figure.patch.set_alpha(1.0)
        axis.set_facecolor(dark_color)
        mesh = axis.pcolormesh(
            x_edges,
            y_edges,
            histogram_for_plot.T,
            shading="auto",
            norm=norm,
            cmap=cmap,
            rasterized=True,
            zorder=1,
        )
        colorbar = figure.colorbar(
            mesh,
            ax=axis,
            pad=0.018,
            fraction=0.05,
            aspect=28,
        )
        colorbar.set_label(
            "Events per bin", fontsize=11 * ABCD_POSTER_LABEL_SCALE
        )
        if isinstance(norm, LogNorm):
            colorbar.locator = LogLocator(base=10.0, numticks=7)
            colorbar.formatter = LogFormatterMathtext(base=10.0)
            colorbar.update_ticks()
        colorbar.ax.minorticks_off()
        colorbar.ax.tick_params(labelsize=10 * ABCD_POSTER_LABEL_SCALE)
        if colorbar.solids is not None:
            colorbar.solids.set_rasterized(False)

        gap_style = {
            "color": "#707070",
            "alpha": 0.15,
            "linewidth": 0.0,
            "zorder": 2,
        }
        annotation_style = {
            "color": NEUTRAL_DARK,
            "fontsize": 8.5 * ABCD_POSTER_LABEL_SCALE,
            "ha": "center",
            "va": "center",
            "zorder": 5,
            "bbox": {
                "boxstyle": "round,pad=0.12",
                "facecolor": "white",
                "edgecolor": "none",
                "alpha": 0.68,
            },
        }
        if boundaries.x_signal_min > boundaries.x_control_max:
            axis.axvspan(
                boundaries.x_control_max,
                boundaries.x_signal_min,
                **gap_style,
            )
            axis.text(
                0.5 * (boundaries.x_control_max + boundaries.x_signal_min),
                y_low + 0.72 * (y_high - y_low),
                "excluded MET gap",
                rotation=90,
                **annotation_style,
            )
        if boundaries.iso_control_min > boundaries.iso_signal_max:
            axis.axhspan(
                boundaries.iso_signal_max,
                boundaries.iso_control_min,
                **gap_style,
            )
            axis.text(
                x_low + 0.72 * (x_high - x_low),
                0.5 * (boundaries.iso_signal_max + boundaries.iso_control_min),
                "excluded isolation gap",
                **annotation_style,
            )

        boundary_style = {
            "color": NEUTRAL_DARK,
            "linestyle": "--",
            "linewidth": 0.9,
            "alpha": 0.95,
            "zorder": 4,
        }
        axis.axvline(boundaries.x_control_max, **boundary_style)
        if boundaries.x_signal_min != boundaries.x_control_max:
            axis.axvline(boundaries.x_signal_min, **boundary_style)
        axis.axhline(boundaries.iso_signal_max, **boundary_style)
        if boundaries.iso_control_min != boundaries.iso_signal_max:
            axis.axhline(boundaries.iso_control_min, **boundary_style)

        _add_region_label(
            axis,
            (high_x, isolated_y),
            "A",
            counts["A"],
            label_scale=ABCD_POSTER_LABEL_SCALE,
        )
        _add_region_label(
            axis,
            (high_x, nonisolated_y),
            "B",
            counts["B"],
            label_scale=ABCD_POSTER_LABEL_SCALE,
        )
        _add_region_label(
            axis,
            (low_x, isolated_y),
            "C",
            counts["C"],
            label_scale=ABCD_POSTER_LABEL_SCALE,
        )
        _add_region_label(
            axis,
            (low_x, nonisolated_y),
            "D",
            counts["D"],
            label_scale=ABCD_POSTER_LABEL_SCALE,
        )

        axis.set_xlim(x_range)
        axis.set_ylim(isolation_range)
        axis.set_xlabel(
            x_label, fontsize=12 * ABCD_POSTER_LABEL_SCALE, labelpad=6
        )
        axis.set_ylabel(
            isolation_label,
            fontsize=12 * ABCD_POSTER_LABEL_SCALE,
            labelpad=6,
        )
        axis.xaxis.set_major_locator(MaxNLocator(nbins=5))
        axis.yaxis.set_major_locator(MaxNLocator(nbins=5))
        axis.tick_params(
            axis="both",
            which="major",
            labelsize=10 * ABCD_POSTER_LABEL_SCALE,
        )
        figure.suptitle(
            title,
            fontsize=17 * ABCD_POSTER_LABEL_SCALE,
            fontweight="bold",
        )
        axis.set_title(
            subtitle,
            fontsize=11 * ABCD_POSTER_LABEL_SCALE,
            pad=8,
        )
        axis.minorticks_off()
        axis.grid(False)
        save_figure_variants(figure, output)
        plt.close(figure)
    return output


@dataclass
class ABCDDataCollector:
    """Collect isolation and MET after the common tight-ID baseline."""

    isolation_chunks: list[np.ndarray] = field(default_factory=list)
    met_chunks_gev: list[np.ndarray] = field(default_factory=list)
    baseline_events: int = 0

    def update(
        self,
        relative_isolation: ak.Array,
        missing_et_raw: ak.Array,
        baseline_mask: ak.Array,
    ) -> None:
        mask = ak.fill_none(baseline_mask, False)
        isolation = ak.to_numpy(
            ak.fill_none(relative_isolation[mask], np.nan)
        ).astype(np.float64, copy=False)
        met_gev = (
            ak.to_numpy(ak.fill_none(missing_et_raw[mask], np.nan)).astype(
                np.float64, copy=False
            )
            * MEV_TO_GEV
        )
        if isolation.shape != met_gev.shape:
            raise RuntimeError(
                "ABCD isolation and MET arrays do not have the same shape."
            )
        self.baseline_events += int(isolation.size)
        if isolation.size:
            self.isolation_chunks.append(isolation.copy())
            self.met_chunks_gev.append(met_gev.copy())

    def arrays(self) -> tuple[np.ndarray, np.ndarray]:
        if not self.isolation_chunks:
            empty = np.empty(0, dtype=np.float64)
            return empty, empty.copy()
        return (
            np.concatenate(self.isolation_chunks),
            np.concatenate(self.met_chunks_gev),
        )


def print_abcd_result(result: ABCDResult) -> None:
    observed = result.observed_a
    predicted = result.predicted_a
    residual = observed - predicted
    residual_uncertainty = float(
        np.sqrt(result.regions["A"].variance + result.predicted_a_uncertainty**2)
    )
    pull = residual / residual_uncertainty if residual_uncertainty > 0 else float("nan")

    print("\nABCD DATA RESULT")
    print(format_result(result))
    print(f"Observed events in A       : {observed:.3f}")
    print(
        "ABCD background prediction: "
        f"{predicted:.3f} ± {result.predicted_a_uncertainty:.3f}"
    )
    print(f"Raw A - prediction         : {residual:.3f} ± {residual_uncertainty:.3f}")
    print(f"Raw residual / uncertainty: {pull:.3f}")
    print(
        "Interpretation note        : this is a preliminary data-only estimate; "
        "MC closure and signal contamination checks still follow."
    )


def write_abcd_summary(
    output_path: Path, boundaries: ABCDBoundaries, result: ABCDResult
) -> Path:
    summary_path = output_path.with_suffix(".txt")
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "ATLAS Open Data W -> e nu: preliminary ABCD estimate",
        "",
        "Boundaries",
        f"isolated: isolation < {boundaries.iso_signal_max:g}",
        f"non-isolated: isolation >= {boundaries.iso_control_min:g}",
        f"low MET: MET <= {boundaries.x_control_max:g} GeV",
        f"high MET: MET >= {boundaries.x_signal_min:g} GeV",
        "",
        format_result(result),
        "",
        f"Observed A minus prediction: {result.observed_a - result.predicted_a:.3f}",
    ]
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary_path


@dataclass(frozen=True)
class ABCDRunResult:
    analysis: AnalysisSummary
    estimate: ABCDResult
    plot_path: Path
    summary_path: Path


def run_abcd_analysis(config: ABCDAnalysisConfig) -> ABCDRunResult:
    """Run the cut-flow and ABCD estimate with one streaming dataset pass."""

    branches = BranchMap(missing_et=config.met_branch)
    root_files = discover_root_files(config.input_path, config.max_files)
    print(f"Discovered {len(root_files)} ROOT file(s).")
    for index, file_path in enumerate(root_files, start=1):
        print(f"  [{index}] {file_path}")

    tree_name, inspected_events = inspect_file(
        root_files[0], config.tree_name, branches
    )
    print("\nAnalysis settings")
    print(f"  lep_pt conversion       : MeV -> GeV (× {MEV_TO_GEV:g})")
    print(f"  selected-electron pT cut: >= {config.electron_pt_min_gev:g} GeV")
    print(f"  electron eta coverage    : |eta| < {ELECTRON_ABS_ETA_MAX:g}")
    print(
        "  transition-region veto   : "
        f"{CALORIMETER_TRANSITION_ABS_ETA_MIN:g} < |eta| < "
        f"{CALORIMETER_TRANSITION_ABS_ETA_MAX:g}"
    )
    print("  electron identification  : tight ID required")
    print(
        "  cut-flow track isolation: "
        f"lep_ptcone30/lep_pt < {config.track_isolation_max:g}"
    )
    print(f"  MET branch              : {branches.missing_et} (MeV -> GeV)")
    print("  ABCD common baseline    : through tight electron ID")
    print(
        "  ABCD isolated / non-iso : "
        f"< {config.abcd_iso_signal_max:g} / "
        f">= {config.abcd_iso_control_min:g}"
    )
    print(
        "  ABCD low / high MET     : "
        f"<= {config.abcd_met_control_max_gev:g} / "
        f">= {config.abcd_met_signal_min_gev:g} GeV"
    )

    collector = ABCDDataCollector()
    tight_selection = tight_id_selection_name()

    def collect_abcd_data(
        arrays: ak.Array,
        electron: SelectedElectron,
        masks: Mapping[str, ak.Array],
    ) -> None:
        collector.update(
            electron.relative_track_isolation,
            arrays[branches.missing_et],
            masks[tight_selection],
        )

    analysis = process_files(
        root_files=root_files,
        tree_name=tree_name,
        branches=branches,
        step_size=config.step_size,
        electron_pt_min_gev=config.electron_pt_min_gev,
        track_isolation_max=config.track_isolation_max,
        on_chunk=collect_abcd_data,
    )

    processed_events = analysis.cutflow.counts["All events"]
    if len(root_files) == 1 and processed_events != inspected_events:
        raise RuntimeError(
            f"Inspected {inspected_events:,} events but processed "
            f"{processed_events:,}."
        )

    print_lepton_type_summary(analysis.lepton_type_counts)
    print_electron_pt_summary(analysis.electron_pt_diagnostics)
    print_track_isolation_summary(
        analysis.track_isolation_diagnostics, config.track_isolation_max
    )
    analysis.cutflow.print_table()

    isolation, met_gev = collector.arrays()
    if isolation.size == 0:
        raise RuntimeError("No events survived the tight-ID ABCD baseline.")

    boundaries = ABCDBoundaries(
        iso_signal_max=config.abcd_iso_signal_max,
        iso_control_min=config.abcd_iso_control_min,
        x_control_max=config.abcd_met_control_max_gev,
        x_signal_min=config.abcd_met_signal_min_gev,
    )
    print("\n" + summarize_region_assignment(isolation, met_gev, boundaries))
    result = estimate_abcd(isolation, met_gev, boundaries)
    print_abcd_result(result)

    plot_path = plot_abcd_plane(
        isolation=isolation,
        discriminant=met_gev,
        boundaries=boundaries,
        output_path=config.abcd_plot_path,
        x_range=(0.0, 100.0),
        isolation_range=(0.0, 0.50),
    )
    summary_path = write_abcd_summary(plot_path, boundaries, result)
    print("\nPHASE-1 ABCD OUTPUT")
    print(f"ABCD plane : {plot_path.resolve()}")
    print(f"ABCD PDF   : {plot_path.with_suffix('.pdf').resolve()}")
    print(f"Text result: {summary_path.resolve()}")
    print("\nABCD integration complete.")
    print("Next: Monte Carlo closure, contamination and signal-shape studies.")

    return ABCDRunResult(
        analysis=analysis,
        estimate=result,
        plot_path=plot_path,
        summary_path=summary_path,
    )
