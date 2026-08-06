#!/usr/bin/env python3

import argparse
import csv
import sys
from dataclasses import dataclass
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import scienceplots  # noqa: F401


W_MASS_GEV = 80.4
EXPECTED_BINS = 60
HISTOGRAM_MIN_GEV = 0.0
HISTOGRAM_MAX_GEV = 90.0
CSV_COLUMNS = ["bin_low", "bin_high", "bin_center", "density", "count"]

PRIMARY_BLUE = "#4878A6"
ACCENT_ORANGE = "#C44E2C"


@dataclass(frozen=True)
class Histogram:
    low: np.ndarray
    high: np.ndarray
    center: np.ndarray
    density: np.ndarray
    count: np.ndarray
    area: float


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render the idealised W -> e nu transverse-mass histogram."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("output/mt_toy.csv"),
        help="normalised histogram CSV produced by the Rust simulation",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("output/mt_toy.svg"),
        help="output SVG path",
    )
    args = parser.parse_args()

    if args.input.suffix.lower() != ".csv":
        parser.error("--input must name a CSV file with a .csv extension")
    if args.output.suffix.lower() != ".svg":
        parser.error("--output must name an SVG file with a .svg extension")

    return args


def read_histogram(path: Path) -> Histogram:
    try:
        with path.open(newline="", encoding="utf-8") as csv_file:
            reader = csv.DictReader(csv_file)
            if reader.fieldnames != CSV_COLUMNS:
                found = ",".join(reader.fieldnames or [])
                raise ValueError(
                    f"unexpected CSV columns in {path}: '{found}'"
                )
            rows = list(reader)
    except FileNotFoundError as error:
        raise ValueError(f"input CSV does not exist: {path}") from error

    if len(rows) != EXPECTED_BINS:
        raise ValueError(
            f"expected {EXPECTED_BINS} histogram bins, found {len(rows)}"
        )

    try:
        low = np.array([float(row["bin_low"]) for row in rows])
        high = np.array([float(row["bin_high"]) for row in rows])
        center = np.array([float(row["bin_center"]) for row in rows])
        density = np.array([float(row["density"]) for row in rows])
        count = np.array([int(row["count"]) for row in rows])
    except (TypeError, ValueError) as error:
        raise ValueError(f"invalid numeric value in {path}") from error

    widths = high - low
    numeric_columns = (low, high, center, density)
    if not all(np.all(np.isfinite(column)) for column in numeric_columns):
        raise ValueError("histogram contains a non-finite value")
    if np.any(widths <= 0.0):
        raise ValueError("histogram bin widths must be positive")
    if np.any(density < 0.0) or np.any(count < 0):
        raise ValueError("histogram density and counts must be non-negative")
    if not np.allclose(widths, widths[0], rtol=0.0, atol=1.0e-12):
        raise ValueError("histogram bins must have equal width")
    if not np.allclose(high[:-1], low[1:], rtol=0.0, atol=1.0e-12):
        raise ValueError("histogram bins must be contiguous")
    if not np.allclose(center, 0.5 * (low + high), rtol=0.0, atol=1.0e-12):
        raise ValueError("histogram bin centres are inconsistent")
    if not np.isclose(low[0], HISTOGRAM_MIN_GEV, rtol=0.0, atol=1.0e-12):
        raise ValueError("histogram must start at 0 GeV")
    if not np.isclose(high[-1], HISTOGRAM_MAX_GEV, rtol=0.0, atol=1.0e-12):
        raise ValueError("histogram must end at 90 GeV")

    total_count = int(np.sum(count))
    if total_count == 0:
        raise ValueError("histogram contains no events")

    expected_density = count / (total_count * widths)
    if not np.allclose(density, expected_density, rtol=1.0e-12, atol=1.0e-15):
        raise ValueError("density does not match count / (events * bin width)")

    area = float(np.sum(density * widths))
    if not np.isclose(area, 1.0, rtol=0.0, atol=1.0e-12):
        raise ValueError(f"normalised histogram area is {area:.15f}, expected 1")

    return Histogram(low, high, center, density, count, area)


def render_svg(histogram: Histogram, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    widths = histogram.high - histogram.low

    with plt.style.context(["science", "no-latex"]):
        plt.rcParams.update(
            {
                "figure.dpi": 200,
                "savefig.dpi": 600,
                "font.family": "serif",
                "font.size": 14,
                "axes.titlesize": 15,
                "axes.labelsize": 14,
                "xtick.labelsize": 13,
                "ytick.labelsize": 13,
                "legend.fontsize": 11,
                "svg.fonttype": "path",
                "svg.hashsalt": "idealised-w-mt-toy",
            }
        )

        figure, axes = plt.subplots(figsize=(6.6, 4.4), constrained_layout=True)
        figure.patch.set_facecolor("white")
        axes.set_facecolor("white")

        axes.bar(
            histogram.low,
            histogram.density,
            width=widths,
            align="edge",
            color=PRIMARY_BLUE,
            edgecolor=PRIMARY_BLUE,
            linewidth=0.6,
            alpha=0.75,
        )
        axes.axvline(
            W_MASS_GEV,
            color=ACCENT_ORANGE,
            linestyle="--",
            linewidth=1.3,
            label=r"Input $m_W = 80.4$ GeV",
        )

        axes.set_xlim(HISTOGRAM_MIN_GEV, HISTOGRAM_MAX_GEV)
        axes.set_ylim(bottom=0.0)
        axes.set_xticks(np.arange(0.0, 91.0, 10.0))
        axes.set_xlabel(r"Transverse mass $m_T$ [GeV]")
        axes.set_ylabel("Normalised events")
        axes.set_title(r"Idealised $W \rightarrow e\nu$ kinematic toy")
        axes.minorticks_on()
        axes.grid(True, which="major", axis="y", alpha=0.22, linewidth=0.5)
        axes.grid(False, which="minor")
        axes.legend(loc="upper left", frameon=True)

        figure.savefig(
            output_path,
            format="svg",
            bbox_inches="tight",
            metadata={"Date": None},
        )
        plt.close(figure)


def main() -> int:
    args = parse_args()
    try:
        histogram = read_histogram(args.input)
        render_svg(histogram, args.output)
    except (OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    print(f"Input histogram: {args.input}")
    print(f"Events: {int(np.sum(histogram.count))}")
    print(f"Normalised histogram area: {histogram.area:.12f}")
    print(f"SVG written to: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
