#!/usr/bin/env python3
# Schematic recreation inspired by Tonomura et al., PRL 56, 792 (1986),
# Fig. 6. Original micrograph not reproduced; diagram generated from an
# explicit phase model.
"""Generate a stylized electron-holography view of a toroidal magnet."""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import shutil
import tempfile


def _ensure_plotting_environment() -> None:
    """Use the repository's existing uv project when run from its root.

    The repository has no root-level ``pyproject.toml``.  This small bootstrap
    keeps the documented command

        uv run python talk/figures-src/tonomura_torus.py

    working by re-entering the plotting environment under ``talk/notes`` only
    when NumPy or Matplotlib is unavailable in the invoking interpreter.
    """
    required = ("matplotlib", "numpy")
    if all(importlib.util.find_spec(package) is not None for package in required):
        return

    if os.environ.get("TONOMURA_UV_BOOTSTRAPPED") == "1":
        missing = [
            package
            for package in required
            if importlib.util.find_spec(package) is None
        ]
        raise RuntimeError(f"Missing plotting dependencies: {', '.join(missing)}")

    script_path = Path(__file__).resolve()
    talk_dir = script_path.parents[1]
    uv_project = talk_dir / "notes" / "scripts"
    uv_executable = shutil.which("uv")
    if uv_executable is None or not (uv_project / "pyproject.toml").is_file():
        raise RuntimeError(
            "NumPy and Matplotlib are required; the repository uv project "
            "could not be found."
        )

    environment = os.environ.copy()
    environment["TONOMURA_UV_BOOTSTRAPPED"] = "1"
    os.execve(
        uv_executable,
        [
            uv_executable,
            "run",
            "--project",
            str(uv_project),
            "python",
            str(script_path),
        ],
        environment,
    )


# Keep Matplotlib's cache independent of a user's home-directory permissions.
os.environ.setdefault(
    "MPLCONFIGDIR",
    str(Path(tempfile.gettempdir()) / "tonomura-torus-matplotlib"),
)
_ensure_plotting_environment()

import matplotlib as mpl

mpl.use("Agg")
import matplotlib.patheffects as path_effects
import matplotlib.pyplot as plt
import numpy as np


SEED = 1986
IMAGE_PIXELS = 1_200
CENTER = (0.5, 0.5)
R_IN = 0.13
R_OUT = 0.33
EDGE_SOFTNESS = 0.0025

FRINGES_PER_IMAGE = 14
FRINGE_SPACING = 1.0 / FRINGES_PER_IMAGE
K = 2.0 * np.pi / FRINGE_SPACING

# These two maxima of the outside carrier pass through the central hole.
GUIDE_ORDERS = (6, 8)
GUIDE_Y = tuple(order * FRINGE_SPACING for order in GUIDE_ORDERS)
OUTPUT_DIR = (
    Path(__file__).resolve().parents[1] / "public" / "assets" / "figures"
)

STYLE = {
    "figure.figsize": (4.0, 4.0),
    "figure.dpi": 150,
    "savefig.dpi": 300,
    "savefig.transparent": True,
    "svg.image_inline": True,
    "svg.hashsalt": "tonomura-torus",
    "svg.fonttype": "path",
    "pdf.compression": 9,
}


def build_micrograph(phi_hole: float) -> np.ndarray:
    """Return the grayscale schematic generated from the explicit phase."""
    # Resetting the generator on every call makes the film grain pixel-for-
    # pixel identical in the shifted and unshifted variants.
    rng = np.random.default_rng(SEED)
    coordinates = (np.arange(IMAGE_PIXELS, dtype=float) + 0.5) / IMAGE_PIXELS
    x = coordinates[np.newaxis, :]
    y = coordinates[:, np.newaxis]
    radius = np.hypot(x - CENTER[0], y - CENTER[1])

    # The phase is parameterized only in the hole and remains zero outside the
    # torus.  Its value in the opaque annulus is immaterial and left at zero.
    phase = np.where(radius < R_IN, phi_hole, 0.0)
    intensity = 0.5 * (1.0 + np.cos(K * y + phase))

    # Map ideal intensity to a film-like tonal range, preserving the carrier's
    # phase exactly while avoiding pure clipped black and white.
    vignette = 1.0 - 0.055 * (radius / np.sqrt(0.5)) ** 2
    grain = rng.normal(0.0, 0.010, size=radius.shape)
    fringe_field = (0.075 + 0.85 * intensity) * vignette + grain

    # Two tanh transitions approximate a very small Gaussian edge blur.  Their
    # product is one only in the annulus and zero in the transparent regions.
    beyond_inner_edge = 0.5 * (
        1.0 + np.tanh((radius - R_IN) / EDGE_SOFTNESS)
    )
    within_outer_edge = 0.5 * (
        1.0 - np.tanh((radius - R_OUT) / EDGE_SOFTNESS)
    )
    opaque_annulus = beyond_inner_edge * within_outer_edge

    radial_fraction = np.clip((radius - R_IN) / (R_OUT - R_IN), 0.0, 1.0)
    annulus_grain = rng.normal(0.0, 0.004, size=radius.shape)
    annulus_tone = 0.022 + 0.012 * radial_fraction + annulus_grain

    micrograph = (
        (1.0 - opaque_annulus) * fringe_field
        + opaque_annulus * annulus_tone
    )
    return np.clip(micrograph, 0.0, 1.0)


def validate_phase_model(phi_hole: float) -> None:
    """Assert the carrier values along the fixed outside-bright guides."""
    expected_hole_intensity = 0.5 * (1.0 + np.cos(phi_hole))
    for guide_y in GUIDE_Y:
        outside_intensity = 0.5 * (1.0 + np.cos(K * guide_y))
        hole_intensity = 0.5 * (1.0 + np.cos(K * guide_y + phi_hole))
        if not (
            np.isclose(outside_intensity, 1.0, atol=1e-12)
            and np.isclose(
                hole_intensity,
                expected_hole_intensity,
                atol=1e-12,
            )
        ):
            raise AssertionError("Guide line is not aligned to the phase model")


def draw_scale_bar(ax: plt.Axes) -> None:
    """Draw the purely illustrative scale marker in axes coordinates."""
    outline = [
        path_effects.Stroke(linewidth=4.0, foreground="black", alpha=0.72),
        path_effects.Normal(),
    ]
    ax.plot(
        [0.065, 0.225],
        [0.070, 0.070],
        color="#f2f2f2",
        linewidth=2.1,
        solid_capstyle="butt",
        path_effects=outline,
        zorder=4,
    )
    ax.text(
        0.145,
        0.088,
        "2 μm",
        ha="center",
        va="bottom",
        color="#f2f2f2",
        fontsize=8.5,
        fontfamily="DejaVu Sans",
        path_effects=outline,
        zorder=4,
    )


def render(phi_hole: float, out_stem: str) -> tuple[Path, Path]:
    """Render one phase variant and return its SVG and PDF paths."""
    validate_phase_model(phi_hole)
    micrograph = build_micrograph(phi_hole)

    with mpl.rc_context(STYLE):
        fig = plt.figure(figsize=(4.0, 4.0), frameon=False)
        ax = fig.add_axes((0.0, 0.0, 1.0, 1.0))
        ax.imshow(
            micrograph,
            cmap="gray",
            vmin=0.0,
            vmax=1.0,
            origin="lower",
            extent=(0.0, 1.0, 0.0, 1.0),
            interpolation="bilinear",
            rasterized=True,
            zorder=1,
        )

        for guide_y in GUIDE_Y:
            ax.axhline(
                guide_y,
                xmin=0.025,
                xmax=0.975,
                color="#dddddd",
                linewidth=0.65,
                linestyle=(0, (4.0, 4.0)),
                dash_capstyle="butt",
                alpha=0.82,
                zorder=3,
            )

        draw_scale_bar(ax)
        ax.set(xlim=(0.0, 1.0), ylim=(0.0, 1.0))
        ax.set_aspect("equal", adjustable="box")
        ax.set_axis_off()

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        output_stem = OUTPUT_DIR / out_stem
        svg_path = output_stem.with_suffix(".svg")
        pdf_path = output_stem.with_suffix(".pdf")

        fig.savefig(
            svg_path,
            format="svg",
            bbox_inches=None,
            pad_inches=0.0,
            metadata={
                "Creator": "tonomura_torus.py",
                "Description": "Phase-model schematic of a toroidal magnet",
                "Date": None,
            },
        )
        fig.savefig(
            pdf_path,
            format="pdf",
            bbox_inches=None,
            pad_inches=0.0,
            metadata={
                "Creator": "tonomura_torus.py",
                "Title": "Tonomura torus phase schematic",
                "CreationDate": None,
                "ModDate": None,
            },
        )
        plt.close(fig)

    print(f"Wrote {svg_path}")
    print(f"Wrote {pdf_path}")
    return svg_path, pdf_path


def migrate_legacy_outputs() -> None:
    """Move the former single-output pair to the shifted naming scheme."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for suffix in (".svg", ".pdf"):
        legacy_path = OUTPUT_DIR / f"tonomura_torus{suffix}"
        shifted_path = OUTPUT_DIR / f"tonomura_torus_shifted{suffix}"
        if legacy_path.exists():
            legacy_path.replace(shifted_path)
            print(f"Renamed {legacy_path} -> {shifted_path}")


def main() -> None:
    """Generate the shifted and unshifted comparison pair."""
    migrate_legacy_outputs()
    render(np.pi, "tonomura_torus_shifted")
    render(0.0, "tonomura_torus_unshifted")
    print("Phase checks: shifted = 0.5 fringe; unshifted = continuous")


if __name__ == "__main__":
    main()
