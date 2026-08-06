#!/usr/bin/env python3
"""Illustrate the distinct local effects measured by divergence and curl."""

import warnings
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
from matplotlib import font_manager
from matplotlib.patches import Polygon


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


LIMITS = (-1.4, 1.4)
GRID = np.linspace(-0.82, 0.82, 5)
FLOW_TIME = 0.32
INITIAL_HALF_SIZE = 0.23

# Match the palette used by ``figures/conservative_force_geometry.tex``.
ARROW_COLOR = "#000000"
REFERENCE_COLOR = "#000000"
DIVERGENCE_COLOR = "#1F4E79"  # noteblue
CURL_COLOR = (0.75, 0.2625, 0.0)  # orange!70!red!75!black
BORDER_COLOR = "#000000"


def square(half_size: float) -> np.ndarray:
    """Return the counter-clockwise vertices of a centred square."""
    return np.array(
        [
            [-half_size, -half_size],
            [half_size, -half_size],
            [half_size, half_size],
            [-half_size, half_size],
        ]
    )


def draw_material_element(
    ax: plt.Axes,
    transform: np.ndarray,
    accent: str,
) -> None:
    """Draw a small material element before and after the local field flow."""
    initial = square(INITIAL_HALF_SIZE)
    evolved = initial @ transform.T

    ax.add_patch(
        Polygon(
            evolved,
            closed=True,
            facecolor=mpl.colors.to_rgba(accent, 0.07),
            edgecolor=accent,
            linewidth=2.5,
            joinstyle="miter",
            zorder=4,
        )
    )
    ax.add_patch(
        Polygon(
            initial,
            closed=True,
            fill=False,
            edgecolor=REFERENCE_COLOR,
            linewidth=1.2,
            linestyle=(0, (3.0, 2.2)),
            joinstyle="miter",
            zorder=5,
        )
    )
    ax.scatter(0.0, 0.0, s=15, color=ARROW_COLOR, zorder=6)


def main() -> None:
    """Create and save the divergence-versus-curl comparison figure."""
    x_grid, y_grid = np.meshgrid(GRID, GRID)
    centre = np.isclose(x_grid, 0.0) & np.isclose(y_grid, 0.0)

    expansion = np.exp(FLOW_TIME) * np.eye(2)
    rotation = np.array(
        [
            [np.cos(FLOW_TIME), -np.sin(FLOW_TIME)],
            [np.sin(FLOW_TIME), np.cos(FLOW_TIME)],
        ]
    )

    panels = (
        {
            "title": "Divergence",
            "field": r"Vector field  $\mathbf{F}=(x,y,0)$",
            "result": r"$\nabla\!\cdot\!\mathbf{F}=2\quad\mathrm{(scalar)}$",
            "u": x_grid,
            "v": y_grid,
            "transform": expansion,
            "accent": DIVERGENCE_COLOR,
        },
        {
            "title": "Curl",
            "field": r"Vector field  $\mathbf{F}=(-y,x,0)$",
            "result": (
                r"$\nabla\!\times\!\mathbf{F}="
                r"2\hat{\mathbf{z}}\quad\mathrm{(vector)}$"
            ),
            "u": -y_grid,
            "v": x_grid,
            "transform": rotation,
            "accent": CURL_COLOR,
        },
    )

    style = FONT_SETTINGS | {
        "font.size": 16,
        "axes.titlesize": 22,
        "axes.titleweight": "semibold",
        "axes.edgecolor": BORDER_COLOR,
        "axes.linewidth": 0.55,
    }

    with mpl.rc_context(style):
        fig, axes = plt.subplots(
            1,
            2,
            figsize=(10.2, 4.6),
            constrained_layout=True,
        )
        fig.set_facecolor("white")

        for ax, panel in zip(axes, panels):
            u = np.ma.array(panel["u"], mask=centre)
            v = np.ma.array(panel["v"], mask=centre)

            ax.quiver(
                x_grid,
                y_grid,
                u,
                v,
                angles="xy",
                scale_units="xy",
                scale=2.8,
                pivot="mid",
                color=ARROW_COLOR,
                width=0.0075,
                headwidth=3.7,
                headlength=4.8,
                headaxislength=4.3,
                minlength=0,
                zorder=2,
            )

            draw_material_element(ax, panel["transform"], panel["accent"])

            ax.set_title(panel["title"], pad=13)
            ax.text(
                0.0,
                1.24,
                panel["field"],
                ha="center",
                va="center",
                fontsize=17,
                color=ARROW_COLOR,
            )
            ax.text(
                0.0,
                -1.24,
                panel["result"],
                ha="center",
                va="center",
                fontsize=16,
                color=ARROW_COLOR,
                bbox={
                    "boxstyle": "round,pad=0.38",
                    "facecolor": mpl.colors.to_rgba(panel["accent"], 0.07),
                    "edgecolor": panel["accent"],
                    "linewidth": 1.2,
                },
            )

            ax.set_xlim(LIMITS)
            ax.set_ylim(LIMITS)
            ax.set_aspect("equal")
            ax.set_xticks([])
            ax.set_yticks([])
            ax.tick_params(bottom=False, left=False)

        output_dir = Path(__file__).resolve().parent
        fig.savefig(output_dir / "divergence_curl.pdf", bbox_inches="tight")
        fig.savefig(
            output_dir / "divergence_curl.png",
            dpi=300,
            bbox_inches="tight",
        )
        plt.close(fig)


if __name__ == "__main__":
    main()
