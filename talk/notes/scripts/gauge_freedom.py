#!/usr/bin/env python3
"""Compare two vector potentials that produce the same uniform magnetic field."""

import warnings
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
from matplotlib import font_manager


STIX_TWO = "STIX Two Text"
FONT_SETTINGS = {
    "font.family": STIX_TWO,
    "mathtext.fontset": "custom",
    "mathtext.rm": STIX_TWO,
    "mathtext.it": f"{STIX_TWO}:italic",
    "mathtext.bf": f"{STIX_TWO}:bold",
}

if STIX_TWO not in {font.name for font in font_manager.fontManager.ttflist}:
    warnings.warn(
        '"STIX Two Text" is unavailable; using Matplotlib\'s bundled STIX fonts.',
        RuntimeWarning,
        stacklevel=2,
    )
    FONT_SETTINGS = {
        "font.family": "STIXGeneral",
        "mathtext.fontset": "stix",
    }


B0 = 1.0
LIMITS = (-2.5, 2.5)
SAMPLES = np.linspace(-2.1, 2.1, 9)

# Arrow lengths are compressed as |A|**COMPRESSION and drawn with a single
# shared scale, so the two panels stay directly comparable while the weak and
# the strong regions of each field both remain readable.
COMPRESSION = 0.6
ARROW_SCALE = 3.4

# Row of field markers sitting just above each panel, in axes coordinates.
SYMBOL_ROW_Y = 1.07
SYMBOL_ROW_X = np.linspace(0.14, 0.86, 7)

# Palette shared with ``divergence_curl.py``.
ARROW_COLOR = "#000000"
SYMMETRIC_COLOR = "#1F4E79"  # noteblue
LANDAU_COLOR = (0.75, 0.2625, 0.0)  # orange!70!red!75!black
FIELD_COLOR = "#1F4E79"
BORDER_COLOR = "#000000"


def compressed_quiver_components(
    u: np.ndarray,
    v: np.ndarray,
) -> tuple[np.ma.MaskedArray, np.ma.MaskedArray]:
    """Rescale ``(u, v)`` to length ``|A|**COMPRESSION``, keeping directions.

    Points where the field vanishes are masked out rather than drawn as
    degenerate arrows.
    """
    magnitude = np.hypot(u, v)
    vanishing = np.isclose(magnitude, 0.0)
    safe = np.where(vanishing, 1.0, magnitude)
    factor = safe ** (COMPRESSION - 1.0)
    return (
        np.ma.array(u * factor, mask=vanishing),
        np.ma.array(v * factor, mask=vanishing),
    )


def draw_field_symbols(ax: plt.Axes) -> None:
    """Draw a row of circled dots marking B pointing out of the page.

    The markers are drawn as point-sized scatter markers rather than as text,
    so the figure depends neither on a "circled dot" glyph being present in the
    chosen font nor on the axes being exactly square. The row is identical in
    both panels, because the magnetic field is.
    """
    row_y = np.full_like(SYMBOL_ROW_X, SYMBOL_ROW_Y)

    ax.scatter(  # outer circle
        SYMBOL_ROW_X,
        row_y,
        transform=ax.transAxes,
        s=190,
        facecolors="white",
        edgecolors=FIELD_COLOR,
        linewidths=1.3,
        clip_on=False,
        zorder=5,
    )
    ax.scatter(  # central dot: B points towards the reader
        SYMBOL_ROW_X,
        row_y,
        transform=ax.transAxes,
        s=16,
        color=FIELD_COLOR,
        clip_on=False,
        zorder=6,
    )


def main() -> None:
    """Create and save the gauge-freedom comparison figure."""
    x_grid, y_grid = np.meshgrid(SAMPLES, SAMPLES)

    # Symmetric gauge and Landau gauge. The two differ by the gradient of
    # chi = B0*x*y/2, i.e. they are related by a gauge transformation, and so
    # they share the same curl, B0 z-hat.
    symmetric = (-B0 * y_grid / 2.0, B0 * x_grid / 2.0)
    landau = (np.zeros_like(x_grid), B0 * x_grid)

    panels = (
        {
            "title": "Symmetric gauge",
            "components": symmetric,
            "formula": r"$\mathbf{A}_1=\dfrac{B_0}{2}\,(-y,\;x,\;0)$",
            "accent": SYMMETRIC_COLOR,
        },
        {
            "title": "Landau gauge",
            "components": landau,
            "formula": r"$\mathbf{A}_2=(0,\;B_0\,x,\;0)$",
            "accent": LANDAU_COLOR,
        },
    )

    style = FONT_SETTINGS | {
        "font.size": 15,
        "axes.titlesize": 20,
        "axes.titleweight": "semibold",
        "axes.labelsize": 17,
        "axes.edgecolor": BORDER_COLOR,
        "axes.linewidth": 0.55,
        "xtick.labelsize": 13,
        "ytick.labelsize": 13,
        "xtick.direction": "in",
        "ytick.direction": "in",
        "xtick.top": True,
        "ytick.right": True,
    }

    with mpl.rc_context(style):
        # Explicit margins rather than constrained_layout: the marker rows and
        # the formula boxes live outside the axes, where automatic layout
        # cannot see them.
        fig, axes = plt.subplots(1, 2, figsize=(9.6, 6.6), sharey=True)
        fig.set_facecolor("white")
        fig.subplots_adjust(
            left=0.085,
            right=0.985,
            top=0.845,
            bottom=0.275,
            wspace=0.12,
        )

        for ax, panel in zip(axes, panels):
            u, v = compressed_quiver_components(*panel["components"])

            ax.quiver(
                x_grid,
                y_grid,
                u,
                v,
                angles="xy",
                scale_units="xy",
                scale=ARROW_SCALE,
                pivot="mid",
                color=ARROW_COLOR,
                width=0.0065,
                headwidth=3.7,
                headlength=4.8,
                headaxislength=4.3,
                minlength=0,
                zorder=2,
            )

            # Same B field in both panels: identical row of circled dots.
            draw_field_symbols(ax)

            ax.set_title(panel["title"], pad=34)
            # Formula sits below the x label, clear of the arrows.
            ax.text(
                0.5,
                -0.15,
                panel["formula"],
                transform=ax.transAxes,
                ha="center",
                va="top",
                fontsize=16,
                color=ARROW_COLOR,
                clip_on=False,
                zorder=7,
                bbox={
                    "boxstyle": "round,pad=0.34",
                    "facecolor": mpl.colors.to_rgba(panel["accent"], 0.07),
                    "edgecolor": panel["accent"],
                    "linewidth": 1.2,
                },
            )

            ax.set_xlim(LIMITS)
            ax.set_ylim(LIMITS)
            ax.set_aspect("equal")
            ax.set_xlabel(r"$x$", labelpad=2)
            ax.set_xticks([-2, -1, 0, 1, 2])
            ax.set_yticks([-2, -1, 0, 1, 2])
            ax.tick_params(length=3.5, width=0.55)

        axes[0].set_ylabel(r"$y$")

        # Common annotations: the two gauges describe one and the same field.
        fig.text(
            0.5,
            0.955,
            "Same uniform magnetic field, out of the page",
            ha="center",
            va="bottom",
            fontsize=16,
            color=FIELD_COLOR,
        )
        fig.text(
            0.5,
            0.035,
            r"$\nabla\times\mathbf{A}_1=\nabla\times\mathbf{A}_2"
            r"=B_0\,\hat{\mathbf{z}}$",
            ha="center",
            va="bottom",
            fontsize=18,
            color=ARROW_COLOR,
        )

        output_dir = Path(__file__).resolve().parent
        for suffix in ("pdf", "svg"):
            fig.savefig(
                output_dir / f"gauge_freedom.{suffix}",
                bbox_inches="tight",
            )
        fig.savefig(
            output_dir / "gauge_freedom.png",
            dpi=300,
            bbox_inches="tight",
        )
        plt.close(fig)


if __name__ == "__main__":
    main()
