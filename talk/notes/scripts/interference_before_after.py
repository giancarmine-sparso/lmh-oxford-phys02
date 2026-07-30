#!/usr/bin/env python3
"""Aharonov--Bohm half-flux-quantum shift from single-electron events.

The physical coordinate ``y`` is shown horizontally, while the uniformly
illuminated detector coordinate ``x`` is shown vertically.  Consequently the
maxima of I(y) appear as vertical fringes, matching the vertical reference
lines used in both panels.
"""

from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np


# Physics and Monte Carlo parameters (dimensionless detector coordinates).
SEED = 20260729
N_ELECTRONS = 8_000
FRINGE_PERIOD = 1.0
ENVELOPE_SIGMA = 2.25
Y_LIMITS = (-3.35, 3.35)
X_LIMITS = (-1.0, 1.0)
PHASES = (0.0, np.pi)

# A small detector-resolution blur, much narrower than one fringe.
Y_JITTER_SIGMA = 0.010 * FRINGE_PERIOD
X_JITTER_SIGMA = 0.004 * (X_LIMITS[1] - X_LIMITS[0])

# Publication palette: conventional steel blue on a near-black detector.
BACKGROUND = "#111418"
ELECTRON_COLOR = "#6E9FC5"
REFERENCE_COLOR = "#F5F7FA"


def intensity(y: np.ndarray, phase: float) -> np.ndarray:
    """Return the unnormalised intensity for a given AB phase shift."""
    envelope = np.exp(-0.5 * (y / ENVELOPE_SIGMA) ** 2)
    carrier = 1.0 + np.cos(2.0 * np.pi * y / FRINGE_PERIOD + phase)
    return carrier * envelope


def sample_y(
    rng: np.random.Generator,
    n_events: int,
    phase: float,
) -> np.ndarray:
    """Draw event positions from I(y) by rejection sampling.

    The proposal is uniform over the displayed detector.  Since both the
    Gaussian envelope and ``(1 + cos) / 2`` are at most one, 2 is a valid
    phase-independent rejection bound.
    """
    samples = np.empty(n_events)
    filled = 0

    while filled < n_events:
        # The acceptance is about one third; this usually fills in one pass
        # and remains efficient if the plotting limits are changed slightly.
        batch_size = max(2_048, 3 * (n_events - filled))
        candidates = rng.uniform(*Y_LIMITS, size=batch_size)
        thresholds = rng.uniform(0.0, 2.0, size=batch_size)
        accepted = candidates[thresholds < intensity(candidates, phase)]

        take = min(accepted.size, n_events - filled)
        samples[filled : filled + take] = accepted[:take]
        filled += take

    # Model finite detector resolution without changing the underlying phase.
    samples += rng.normal(0.0, Y_JITTER_SIGMA, size=n_events)
    return np.clip(samples, *Y_LIMITS)


def carrier_maxima(phase: float) -> np.ndarray:
    """Return all ideal carrier maxima inside the displayed y range."""
    offset = -phase * FRINGE_PERIOD / (2.0 * np.pi)
    first_order = int(np.ceil((Y_LIMITS[0] - offset) / FRINGE_PERIOD))
    last_order = int(np.floor((Y_LIMITS[1] - offset) / FRINGE_PERIOD))
    orders = np.arange(first_order, last_order + 1)
    return offset + orders * FRINGE_PERIOD


def histogram_peak_positions(
    samples: np.ndarray,
    expected_positions: np.ndarray,
    n_bins: int = 320,
) -> np.ndarray:
    """Estimate local maxima from a mildly smoothed event histogram.

    Each expected carrier maximum only supplies a non-overlapping search
    window.  A local quadratic fit to the smoothed histogram gives sub-bin
    peak positions and naturally includes the weak pull of the Gaussian
    envelope toward y=0.
    """
    counts, edges = np.histogram(samples, bins=n_bins, range=Y_LIMITS)
    centres = 0.5 * (edges[:-1] + edges[1:])

    kernel_x = np.arange(-8, 9, dtype=float)
    kernel = np.exp(-0.5 * (kernel_x / 2.2) ** 2)
    kernel /= kernel.sum()
    smooth_counts = np.convolve(counts.astype(float), kernel, mode="same")

    estimates: list[float] = []
    for expected in expected_positions:
        search = np.flatnonzero(
            np.abs(centres - expected) < 0.36 * FRINGE_PERIOD
        )
        peak_index = search[np.argmax(smooth_counts[search])]

        fit = np.abs(centres - centres[peak_index]) < 0.17 * FRINGE_PERIOD
        local_y = centres[fit] - centres[peak_index]
        quadratic, linear, _ = np.polyfit(local_y, smooth_counts[fit], 2)

        if quadratic < 0.0:
            estimate = centres[peak_index] - linear / (2.0 * quadratic)
        else:
            estimate = centres[peak_index]

        # A defensive fallback for an anomalous fit in a very sparse fringe.
        if abs(estimate - expected) >= 0.36 * FRINGE_PERIOD:
            estimate = centres[peak_index]
        estimates.append(float(estimate))

    return np.asarray(estimates)


def print_histogram_check(before_y: np.ndarray, after_y: np.ndarray) -> None:
    """Print the first three measured maxima and the half-period check."""
    before_peaks = histogram_peak_positions(before_y, carrier_maxima(PHASES[0]))
    after_peaks = histogram_peak_positions(after_y, carrier_maxima(PHASES[1]))

    # In the finite displayed window, the first three left-to-right peaks of
    # the After panel lie half a period to the right of the corresponding
    # first three peaks in the Before panel.
    before_first = before_peaks[:3]
    after_first = after_peaks[:3]
    shifts = after_first - before_first
    mean_shift = float(np.mean(shifts))
    expected_shift = 0.5 * FRINGE_PERIOD
    tolerance = 0.08 * FRINGE_PERIOD
    passed = bool(np.all(np.abs(shifts - expected_shift) < tolerance))

    formatted_before = np.array2string(before_first, precision=3, separator=", ")
    formatted_after = np.array2string(after_first, precision=3, separator=", ")
    formatted_shifts = np.array2string(shifts, precision=3, separator=", ")

    print("Histogram peak check (detector y units)")
    print(f"  Before, first 3 maxima: {formatted_before}")
    print(f"  After,  first 3 maxima: {formatted_after}")
    print(f"  After - Before shifts:  {formatted_shifts}")
    print(
        f"  Mean shift = {mean_shift:.3f}; expected Lambda/2 = "
        f"{expected_shift:.3f} -> {'PASS' if passed else 'CHECK'}"
    )


def main() -> None:
    """Generate the two-panel event accumulation and save PNG and PDF."""
    rng = np.random.default_rng(SEED)
    y_events = [sample_y(rng, N_ELECTRONS, phase) for phase in PHASES]
    x_events = []
    for _ in PHASES:
        detector_x = rng.uniform(*X_LIMITS, size=N_ELECTRONS)
        detector_x += rng.normal(0.0, X_JITTER_SIGMA, size=N_ELECTRONS)
        x_events.append(np.clip(detector_x, *X_LIMITS))

    style = {
        "font.family": "DejaVu Sans",
        "font.size": 15,
        "axes.titlesize": 18,
        "axes.titleweight": "bold",
        "axes.titlecolor": REFERENCE_COLOR,
        "savefig.facecolor": BACKGROUND,
    }

    with mpl.rc_context(style):
        fig, axes = plt.subplots(1, 2, figsize=(12.0, 4.0), facecolor=BACKGROUND)
        fig.subplots_adjust(
            left=0.018,
            right=0.982,
            bottom=0.055,
            top=0.84,
            wspace=0.14,
        )

        before_guides = carrier_maxima(PHASES[0])
        for ax, title, detector_x, detector_y in zip(
            axes,
            ("Before", "After"),
            x_events,
            y_events,
        ):
            ax.set_facecolor(BACKGROUND)

            # Identical Before-maximum references in both panels.  A modest
            # alpha keeps them readable even where they cross a dense fringe.
            for maximum in before_guides:
                ax.axvline(
                    maximum,
                    color=REFERENCE_COLOR,
                    linewidth=0.85,
                    linestyle=(0, (3.0, 4.2)),
                    alpha=0.43,
                    zorder=3,
                )

            # Rasterising only the dense event cloud keeps the PDF compact;
            # titles and reference guides remain vector graphics.
            ax.scatter(
                detector_y,
                detector_x,
                s=1.5,
                color=ELECTRON_COLOR,
                alpha=0.62,
                edgecolors="none",
                linewidths=0.0,
                rasterized=True,
                zorder=2,
            )

            ax.set_title(title, pad=10)
            ax.set_xlim(Y_LIMITS)
            ax.set_ylim(X_LIMITS)
            ax.set_xticks([])
            ax.set_yticks([])
            ax.tick_params(bottom=False, left=False)
            for spine in ax.spines.values():
                spine.set_visible(False)

        output_dir = Path(__file__).resolve().parent / "figures"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_stem = output_dir / "interference_before_after"
        fig.savefig(output_stem.with_suffix(".png"), dpi=300)
        fig.savefig(output_stem.with_suffix(".pdf"), dpi=300)
        plt.close(fig)

    print_histogram_check(y_events[0], y_events[1])


if __name__ == "__main__":
    main()
