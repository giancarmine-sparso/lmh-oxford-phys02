#!/usr/bin/env python3
"""Illustrate the relation between a potential gradient and its force."""

import warnings
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
from matplotlib import font_manager
from matplotlib.colors import LinearSegmentedColormap


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


XLIM = (-2.5, 2.5)
YLIM = (0.0, 5.0)
ARROW_LENGTH = 0.62


def truncate(name: str, lo: float, hi: float) -> LinearSegmentedColormap:
    """Return a colormap restricted to the interval ``[lo, hi]``."""
    base = mpl.colormaps[name]
    colors = base(np.linspace(lo, hi, 256))
    return LinearSegmentedColormap.from_list(f"{name}_{lo:.2f}_{hi:.2f}", colors)


CMAP = truncate("viridis", 0.10, 0.80)


def main() -> None:
    """Create and save the uniform-gravity gradient/force figure."""
    m = 1.0
    g = 1.0

    # Construct the scalar potential U(x, y) = m g y on a fine grid.
    x = np.linspace(*XLIM, 301)
    y = np.linspace(*YLIM, 301)
    _, Y = np.meshgrid(x, y)
    U = m * g * Y
    u_min = m * g * YLIM[0]
    u_max = m * g * YLIM[1]

    # Sample grad(U) = (0, m g); display each arrow at 0.62 data units.
    arrow_x = np.linspace(-2.0, 2.0, 5)
    arrow_y = np.linspace(0.65, 3.85, 5)
    Xq, Yq = np.meshgrid(arrow_x, arrow_y)
    grad_u_x = np.zeros_like(Xq)
    grad_u_y = np.full_like(Yq, np.sign(m * g) * ARROW_LENGTH)

    # The gravitational force reverses the gradient: F = -grad(U).
    force_x = -grad_u_x
    force_y = -grad_u_y

    style = FONT_SETTINGS | {
        "font.size": 16,
        "axes.titlesize": 19,
        "axes.labelsize": 18,
        "xtick.labelsize": 16,
        "ytick.labelsize": 16,
        "xtick.direction": "in",
        "ytick.direction": "in",
        "xtick.top": True,
        "ytick.right": True,
    }

    with mpl.rc_context(style):
        fig, axes = plt.subplots(
            1,
            2,
            figsize=(10.2, 4.6),
            sharey=True,
            constrained_layout=True,
        )

        panel_data = (
            (
                "Gradient of the potential energy",
                grad_u_x,
                grad_u_y,
                r"$\nabla U$",
            ),
            (
                "Gravitational force",
                force_x,
                force_y,
                r"$\mathbf{F} = -\nabla U$",
            ),
        )

        for ax, (title, vector_x, vector_y, label) in zip(axes, panel_data):
            im = ax.imshow(
                U,
                interpolation="bilinear",
                origin="lower",
                extent=(*XLIM, *YLIM),
                cmap=CMAP,
                vmin=u_min,
                vmax=u_max,
                rasterized=True,
            )

            ax.quiver(
                Xq,
                Yq,
                vector_x,
                vector_y,
                angles="xy",
                scale_units="xy",
                scale=1,
                pivot="mid",
                color="white",
                edgecolor="0.15",
                linewidth=0.7,
                width=0.012,
                headwidth=4.4,
                headlength=5.2,
                headaxislength=4.8,
            )

            ax.text(
                0.05,
                0.95,
                label,
                transform=ax.transAxes,
                ha="left",
                va="top",
                fontsize=18,
                color="#202020",
                bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.82},
            )
            ax.set_title(title, pad=10)
            ax.set_xlabel(r"$x$")
            ax.set_xlim(XLIM)
            ax.set_ylim(YLIM)
            ax.set_aspect("equal")
            ax.tick_params(color="white", length=4.0, width=0.8)

        axes[0].set_ylabel(r"$y$")

        colorbar = fig.colorbar(im, ax=axes)
        colorbar.solids.set_rasterized(False)
        colorbar.set_label(r"Potential energy $U$ (a.u.)")

        output_dir = Path(__file__).resolve().parent
        fig.savefig(output_dir / "gravitational_gradient.pdf", bbox_inches="tight")
        fig.savefig(
            output_dir / "gravitational_gradient.png",
            dpi=300,
            bbox_inches="tight",
        )
        plt.close(fig)


if __name__ == "__main__":
    main()
