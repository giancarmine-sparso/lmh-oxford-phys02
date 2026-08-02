#!/usr/bin/env python3
"""Conceptual figure: a field is revealed by the response of a probe.

Run from the repository root::

    uv run --project talk/scripts python talk/scripts/generate_field_probe_concept.py

Writes ``talk/assets/figures/field-probe-concept.{svg,png}``.
"""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import shutil
import tempfile


def _ensure_plotting_environment() -> None:
    """Re-enter the ``talk/scripts`` uv project if NumPy/Matplotlib are absent.

    The repository has no root-level ``pyproject.toml``, so a bare
    ``python talk/scripts/generate_field_probe_concept.py`` from the repository
    root would otherwise fail on the import of Matplotlib.
    """
    required = ("matplotlib", "numpy")
    if all(importlib.util.find_spec(package) is not None for package in required):
        return

    if os.environ.get("FIELD_PROBE_UV_BOOTSTRAPPED") == "1":
        missing = [
            package
            for package in required
            if importlib.util.find_spec(package) is None
        ]
        raise RuntimeError(f"Missing plotting dependencies: {', '.join(missing)}")

    script_path = Path(__file__).resolve()
    uv_project = script_path.parent
    uv_executable = shutil.which("uv")
    if uv_executable is None or not (uv_project / "pyproject.toml").is_file():
        raise RuntimeError(
            "NumPy and Matplotlib are required; the repository uv project "
            "could not be found."
        )

    environment = os.environ.copy()
    environment["FIELD_PROBE_UV_BOOTSTRAPPED"] = "1"
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
    str(Path(tempfile.gettempdir()) / "field-probe-matplotlib"),
)
_ensure_plotting_environment()

import matplotlib as mpl

mpl.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Circle, FancyArrowPatch


OUTPUT_DIR = Path(__file__).resolve().parents[1] / "assets" / "figures"
STEM = "field-probe-concept"

# 16:9 canvas, sized for a projected Reveal.js slide.
WIDTH, HEIGHT = 16.0, 9.0
FIGSIZE = (12.0, 6.75)

INK = "#17191d"
SOURCE_COLOR = "#111c28"
GRID_COLOR = "#dbe1e8"
FIELD_COLOR = "#37699a"
ACCENT = "#bf4f2c"
MUTED = "#5b6b7c"

SOURCE = np.array([3.45, 3.30])
SOURCE_RADIUS = 0.40
PROBE = np.array([10.25, 5.95])
PROBE_RADIUS = 0.215
RESPONSE_LENGTH = 2.30

INSET_CENTER = np.array([13.45, 6.55])
INSET_RADIUS = 1.18

STYLE = {
    "figure.figsize": FIGSIZE,
    "figure.dpi": 150,
    "savefig.dpi": 200,
    "savefig.transparent": True,
    "font.family": "serif",
    "font.serif": ["STIX Two Text", "STIXGeneral", "DejaVu Serif"],
    "mathtext.fontset": "stix",
    "svg.fonttype": "path",
    "svg.hashsalt": STEM,
}


def unit(vector: np.ndarray) -> np.ndarray:
    """Return the unit vector along ``vector``."""
    return vector / np.linalg.norm(vector)


def field_direction(points: np.ndarray) -> np.ndarray:
    """Unit vectors of the (attractive) field, pointing back at the source."""
    offset = SOURCE - points
    return offset / np.linalg.norm(offset, axis=-1, keepdims=True)


def field_strength(points: np.ndarray) -> np.ndarray:
    """Monotonically decaying strength used for arrow length and opacity.

    A true inverse square decays far too fast to stay legible across the frame,
    so the drawing uses a gentler power of the distance.  Only the qualitative
    statement "the field varies from point to point" has to survive.
    """
    radius = np.linalg.norm(points - SOURCE, axis=-1)
    return 1.0 / np.maximum(radius, 1e-6) ** 0.62


def warp(points: np.ndarray) -> np.ndarray:
    """Pull the background grid gently towards the source.

    The displacement is deliberately small and dies off over a few units, so
    the grid still reads as ordinary space with a structure imprinted on it,
    not as a curved spacetime diagram.
    """
    offset = points - SOURCE
    radius = np.linalg.norm(offset, axis=-1, keepdims=True)
    direction = offset / np.maximum(radius, 1e-9)
    amplitude = 0.40 * np.exp(-(radius**2) / (2.0 * 3.1**2))
    return points - direction * amplitude


def draw_field_haze(ax: plt.Axes) -> None:
    """Lay a very faint tint over space, densest where the field is strongest.

    Built from nested translucent discs rather than an image, so the SVG stays
    fully vectorial and small.  Each disc gets the opacity that turns the
    accumulated tint into the intended radial profile.
    """
    radii = np.linspace(19.0, 0.0, 90)
    profile = 1.0 / (radii + 1.1) ** 1.35
    target = 0.30 * profile / profile.max()

    accumulated = 0.0
    for radius, opacity in zip(radii, target):
        alpha = (opacity - accumulated) / (1.0 - accumulated)
        accumulated = opacity
        if alpha <= 0.0:
            continue
        ax.add_patch(
            Circle(
                SOURCE,
                radius,
                facecolor=FIELD_COLOR,
                edgecolor="none",
                alpha=float(alpha),
                zorder=0,
            )
        )


def draw_space_grid(ax: plt.Axes) -> None:
    """Draw the warped coordinate grid that stands for space itself."""
    samples = 300
    for x0 in np.arange(0.5, WIDTH + 0.01, 1.0):
        line = np.stack(
            [np.full(samples, x0), np.linspace(0.0, HEIGHT, samples)], axis=-1
        )
        warped = warp(line)
        ax.plot(
            warped[:, 0], warped[:, 1], color=GRID_COLOR, linewidth=0.75, zorder=1
        )
    for y0 in np.arange(0.5, HEIGHT + 0.01, 1.0):
        line = np.stack(
            [np.linspace(0.0, WIDTH, samples), np.full(samples, y0)], axis=-1
        )
        warped = warp(line)
        ax.plot(
            warped[:, 0], warped[:, 1], color=GRID_COLOR, linewidth=0.75, zorder=1
        )


def draw_field_lines(ax: plt.Axes) -> None:
    """A restrained set of radial field lines, fading out with distance.

    They are drawn segment by segment so that the opacity can follow the field
    strength; at full length they would compete with the grid.
    """
    radii = np.linspace(0.60, 7.2, 40)
    for angle in np.arange(0.0, 2.0 * np.pi, np.pi / 6.0):
        direction = np.array([np.cos(angle), np.sin(angle)])
        points = SOURCE + radii[:, None] * direction
        for start, end, radius in zip(points[:-1], points[1:], radii[:-1]):
            alpha = 0.13 * float(np.exp(-((radius / 4.4) ** 2)))
            ax.plot(
                [start[0], end[0]],
                [start[1], end[1]],
                color=FIELD_COLOR,
                linewidth=0.7,
                alpha=alpha,
                solid_capstyle="butt",
                zorder=2,
            )


def _keep_out(point: np.ndarray) -> bool:
    """True where a field arrow would collide with a labelled element."""
    if np.linalg.norm(point - SOURCE) < 1.35:
        return True
    if np.linalg.norm(point - PROBE) < 1.15:
        return True
    if np.linalg.norm(point - INSET_CENTER) < INSET_RADIUS + 0.75:
        return True
    if point[1] < 1.25 or point[1] > 8.35 or point[0] < 0.55 or point[0] > 15.5:
        return True

    # Corridor reserved for the response arrow and its label.
    towards_source = unit(SOURCE - PROBE)
    along = float(np.dot(point - PROBE, towards_source))
    if -0.4 < along < RESPONSE_LENGTH + 0.9:
        across = np.linalg.norm(point - PROBE - along * towards_source)
        if across < 1.05:
            return True

    # Text boxes: "source", "field", and the caption under the magnifier.
    for centre, half in (
        (np.array([3.45, 2.45]), np.array([0.85, 0.45])),
        (np.array([12.95, 2.30]), np.array([0.75, 0.45])),
        (INSET_CENTER - np.array([0.0, INSET_RADIUS + 0.45]), np.array([2.1, 0.55])),
    ):
        if np.all(np.abs(point - centre) < half):
            return True
    return False


def draw_field_arrows(ax: plt.Axes) -> None:
    """The field itself: one small arrow attached to each sampled point."""
    spacing = 1.28
    reference = field_strength(np.array([[2.0, 3.3]]))[0]

    for row, y in enumerate(np.arange(1.0, HEIGHT, spacing * 0.82)):
        offset = 0.5 * spacing * (row % 2)
        for x in np.arange(0.75 + offset, WIDTH, spacing):
            point = np.array([x, y])
            if _keep_out(point):
                continue

            strength = field_strength(point[None, :])[0] / reference
            length = float(np.clip(0.95 * strength**0.85, 0.30, 0.86))
            alpha = float(np.clip(0.90 * strength**0.8, 0.24, 0.82))
            direction = field_direction(point[None, :])[0]

            tail = point - 0.5 * length * direction
            head = point + 0.5 * length * direction
            ax.add_patch(
                FancyArrowPatch(
                    tail,
                    head,
                    arrowstyle="-|>",
                    mutation_scale=6.0 + 7.0 * length,
                    linewidth=0.9 + 0.7 * length,
                    color=FIELD_COLOR,
                    alpha=alpha,
                    shrinkA=0.0,
                    shrinkB=0.0,
                    zorder=3,
                )
            )


def draw_source(ax: plt.Axes) -> None:
    """A minimal filled disc, with a halo that hides the grid convergence."""
    ax.add_patch(
        Circle(SOURCE, 0.72, facecolor="white", edgecolor="none", alpha=0.85, zorder=4)
    )
    ax.add_patch(
        Circle(
            SOURCE,
            SOURCE_RADIUS + 0.16,
            facecolor=FIELD_COLOR,
            edgecolor="none",
            alpha=0.16,
            zorder=4,
        )
    )
    ax.add_patch(
        Circle(SOURCE, SOURCE_RADIUS, facecolor=SOURCE_COLOR, edgecolor="none", zorder=5)
    )
    ax.text(
        SOURCE[0],
        SOURCE[1] - 0.82,
        "source",
        ha="center",
        va="top",
        fontsize=13.5,
        color=INK,
        zorder=6,
    )


def draw_probe(ax: plt.Axes) -> None:
    """The test object that turns the field into something observable."""
    ax.add_patch(
        Circle(PROBE, 0.46, facecolor=ACCENT, edgecolor="none", alpha=0.13, zorder=5)
    )
    ax.add_patch(
        Circle(
            PROBE,
            PROBE_RADIUS,
            facecolor="#fffaf6",
            edgecolor=ACCENT,
            linewidth=2.1,
            zorder=7,
        )
    )
    ax.text(
        PROBE[0] + 0.05,
        PROBE[1] + 0.52,
        "probe",
        ha="left",
        va="bottom",
        fontsize=13.5,
        color=INK,
        zorder=7,
    )


def draw_response(ax: plt.Axes) -> None:
    """The response vector: same direction as the local field, but emphasized."""
    direction = unit(SOURCE - PROBE)
    tail = PROBE + PROBE_RADIUS * 1.35 * direction
    head = PROBE + RESPONSE_LENGTH * direction
    ax.add_patch(
        FancyArrowPatch(
            tail,
            head,
            arrowstyle="-|>",
            mutation_scale=22.0,
            linewidth=2.6,
            color=ACCENT,
            shrinkA=0.0,
            shrinkB=0.0,
            zorder=7,
        )
    )

    normal = np.array([direction[1], -direction[0]])
    if normal[1] > 0:  # keep the label below the arrow
        normal = -normal
    anchor = PROBE + 0.52 * RESPONSE_LENGTH * direction + 0.42 * normal
    angle = float(np.degrees(np.arctan2(direction[1], direction[0])) + 180.0)
    ax.text(
        anchor[0],
        anchor[1],
        "measurable response",
        ha="center",
        va="top",
        rotation=angle,
        rotation_mode="anchor",
        fontsize=13.0,
        color=ACCENT,
        zorder=7,
    )


def draw_callout(ax: plt.Axes) -> None:
    """A small magnifier: the local field at the probe, and what it produces."""
    direction = unit(INSET_CENTER - PROBE)
    normal = np.array([-direction[1], direction[0]])
    ring_radius = 0.58

    for sign in (+1.0, -1.0):
        start = PROBE + sign * ring_radius * normal
        end = INSET_CENTER + sign * INSET_RADIUS * normal
        ax.plot(
            [start[0], end[0]],
            [start[1], end[1]],
            color="#c3ccd6",
            linewidth=0.8,
            alpha=0.75,
            zorder=4,
        )
    ax.add_patch(
        Circle(
            PROBE,
            ring_radius,
            facecolor="none",
            edgecolor="#c3ccd6",
            linewidth=0.9,
            zorder=6,
        )
    )
    ax.add_patch(
        Circle(
            INSET_CENTER,
            INSET_RADIUS,
            facecolor="white",
            edgecolor="#c3ccd6",
            linewidth=1.0,
            alpha=0.97,
            zorder=6,
        )
    )

    local = unit(SOURCE - PROBE)
    across = np.array([-local[1], local[0]])

    # Local field: two short parallel arrows, i.e. the field seen up close,
    # left and right of the response so that nothing overlaps.
    for offset in (-0.68, 0.68):
        centre = INSET_CENTER + offset * across + 0.10 * local
        ax.add_patch(
            FancyArrowPatch(
                centre - 0.36 * local,
                centre + 0.36 * local,
                arrowstyle="-|>",
                mutation_scale=8.0,
                linewidth=1.0,
                color=FIELD_COLOR,
                alpha=0.55,
                shrinkA=0.0,
                shrinkB=0.0,
                zorder=7,
            )
        )

    probe_dot = INSET_CENTER - 0.50 * local
    ax.add_patch(
        Circle(
            probe_dot,
            0.115,
            facecolor="white",
            edgecolor=ACCENT,
            linewidth=1.4,
            zorder=8,
        )
    )
    ax.add_patch(
        FancyArrowPatch(
            probe_dot + 0.16 * local,
            probe_dot + 0.92 * local,
            arrowstyle="-|>",
            mutation_scale=13.0,
            linewidth=1.9,
            color=ACCENT,
            shrinkA=0.0,
            shrinkB=0.0,
            zorder=8,
        )
    )

    ax.text(
        INSET_CENTER[0],
        INSET_CENTER[1] - INSET_RADIUS - 0.24,
        r"field at this point  $\rightarrow$  probe response",
        ha="center",
        va="top",
        fontsize=10.0,
        color=MUTED,
        zorder=7,
    )


def draw_text(ax: plt.Axes) -> None:
    """The remaining two words and the conceptual caption."""
    ax.text(
        12.95,
        2.30,
        "field",
        ha="center",
        va="center",
        fontsize=13.5,
        color=FIELD_COLOR,
        zorder=6,
    )
    ax.text(
        WIDTH / 2.0,
        0.42,
        r"Field  $\rightarrow$  probe  $\rightarrow$  observable effect",
        ha="center",
        va="center",
        fontsize=17.0,
        color=MUTED,
        zorder=6,
    )


def render() -> tuple[Path, Path]:
    """Draw the scene once and write both output formats."""
    with mpl.rc_context(STYLE):
        figure, ax = plt.subplots()
        figure.subplots_adjust(left=0.0, right=1.0, bottom=0.0, top=1.0)
        ax.set_xlim(0.0, WIDTH)
        ax.set_ylim(0.0, HEIGHT)
        ax.set_aspect("equal")
        ax.set_axis_off()

        draw_field_haze(ax)
        draw_space_grid(ax)
        draw_field_lines(ax)
        draw_field_arrows(ax)
        draw_source(ax)
        draw_callout(ax)
        draw_response(ax)
        draw_probe(ax)
        draw_text(ax)

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        svg_path = OUTPUT_DIR / f"{STEM}.svg"
        png_path = OUTPUT_DIR / f"{STEM}.png"
        figure.savefig(svg_path, format="svg")
        figure.savefig(png_path, format="png")
        plt.close(figure)

    return svg_path, png_path


if __name__ == "__main__":
    for path in render():
        print(f"wrote {path}")
