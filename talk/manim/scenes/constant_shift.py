"""A constant vertical shift changes potential values, but not their gradient."""

from __future__ import annotations

import numpy as np

from manim import (
    DEGREES,
    PI,
    Arrow,
    Create,
    FadeIn,
    FadeOut,
    Line,
    MathTex,
    ShowPassingFlash,
    Sphere,
    Surface,
    ThreeDAxes,
    ThreeDScene,
    VGroup,
    WHITE,
    config,
    smooth,
)


# Visual theme
BACKGROUND_COLOR = "#090D18"
BASE_MESH_COLOR = WHITE
SCALE_COLOR = "#B7FF3C"
XY_AXIS_COLOR = "#B76880"
TANGENT_COLOR = "#FF70B7"
PARALLEL_FLASH_COLOR = "#FFF0F8"
SOURCE_COLOR = "#FFD166"
SHIFT_COLOR = "#67D4FF"

config.background_color = BACKGROUND_COLOR

# Potential, equipotentials, and sample point
K = 8.0
CONSTANT_SHIFT = 10.0
SURFACE_U_MIN = -20.0
SURFACE_U_MAX = -2.5
SURFACE_U_STEP = 2.5
THETA_MIN = 0.0
THETA_MAX = 2.0 * PI
X0 = 1.6
Y0 = 0.0

# Hidden coordinate system used by the surface and analytic annotations
X_RANGE = (-4.5, 4.5, 1.0)
Y_RANGE = (-4.5, 4.5, 1.0)
Z_RANGE = (-22.5, 10.0, 2.5)
X_LENGTH = 6.7
Y_LENGTH = 6.7
Z_LENGTH = 6.3
X_UNIT_LENGTH = X_LENGTH / (X_RANGE[1] - X_RANGE[0])
Z_UNIT_LENGTH = Z_LENGTH / (Z_RANGE[1] - Z_RANGE[0])
SURFACE_RESOLUTION = (
    int((SURFACE_U_MAX - SURFACE_U_MIN) / SURFACE_U_STEP),
    8,
)
MESH_STROKE_WIDTH = 1.4
MESH_STROKE_OPACITY = 0.80
GHOST_MESH_STROKE_OPACITY = 0.20
GHOST_SOURCE_FADE = 0.75

# Camera.  The focal distance is long enough that the final view is effectively an
# orthographic projection onto the screen basis below, which is what lets the layout
# be solved analytically instead of tuned by eye.
TOP_CAMERA_PHI = 0.0 * DEGREES
FINAL_CAMERA_PHI = 57.0 * DEGREES
CAMERA_THETA = -50.0 * DEGREES
CAMERA_FOCAL_DISTANCE = 500.0
TOP_CAMERA_ZOOM = 1.35
FINAL_CAMERA_ZOOM = 1.10
CAMERA_RIGHT = np.array(
    (-np.sin(CAMERA_THETA), np.cos(CAMERA_THETA), 0.0),
)
CAMERA_UP = np.array(
    (
        -np.cos(FINAL_CAMERA_PHI) * np.cos(CAMERA_THETA),
        -np.cos(FINAL_CAMERA_PHI) * np.sin(CAMERA_THETA),
        np.sin(FINAL_CAMERA_PHI),
    ),
)
SCREEN_BASIS = np.column_stack((CAMERA_RIGHT, CAMERA_UP))
MOUTH_OUTLINE_SAMPLES = 1441

# Fixed-frame reference axes shown after the camera tilt.  The oblique pair is drawn
# with the slopes of the reference composition rather than the true projected x and y
# axes, which would cut straight through the well; the anchor below is the only
# hand-picked value, and the well is then placed so both lines graze its mouth.
DISPLAY_AXES_SCREEN_ORIGIN = np.array((-5.55, 0.40, 0.0))
# One unit of U, measured on screen exactly as the projected well measures it, so the
# +10 arrow is as long as the distance the well actually travels.
DISPLAY_U_UNIT_LENGTH = (
    Z_UNIT_LENGTH * np.sin(FINAL_CAMERA_PHI) * FINAL_CAMERA_ZOOM
)
DISPLAY_XY_NEGATIVE_SPAN = 1.10
DISPLAY_XY_POSITIVE_SPAN = 12.00
DISPLAY_UPPER_AXIS_SLOPE = 0.53
DISPLAY_LOWER_AXIS_SLOPE = -0.56
DISPLAY_AXIS_STROKE_WIDTH = 2.2
DISPLAY_AXIS_TICK_SIZE = 0.060
DISPLAY_XY_OPACITY = 0.62
DISPLAY_Z_OPACITY = 0.88
DISPLAY_AXIS_LABEL_VALUES = (-20.0, -10.0, 0.0, 10.0)
DISPLAY_AXIS_LABEL_FONT_SIZE = 32.0
DISPLAY_AXIS_LABEL_OFFSET = 0.36
DISPLAY_AXIS_NAME_OFFSET = 0.45

# Source, sample marker, and tangent geometry
SOURCE_Z = -21.25
SOURCE_RADIUS = 0.16
SOURCE_GLOW_RADIUS = 0.26
SOURCE_GLOW_OPACITY = 0.18
SAMPLE_RADIUS = 0.105
SAMPLE_GLOW_RADIUS = 0.175
SAMPLE_GLOW_OPACITY = 0.16
MARKER_RESOLUTION = (12, 24)
TANGENT_HALF_SPAN = 0.80
TANGENT_STROKE_WIDTH = 7.0
TANGENT_OPACITY = 0.94
TANGENT_FLASH_WIDTH = 12.0
FLASH_TIME_WIDTH = 0.35

# Shift annotation.  Grazing the mouth leaves no room between the U scale and the
# well — that close to the apex the wedge is narrower than the arrow is long — so the
# arrow stands clear of the mouth's far edge instead, with its label to its right.
SHIFT_ARROW_SCREEN_GAP = 0.55
SHIFT_LABEL_SCREEN_OFFSET = 0.65
SHIFT_ARROW_STROKE_WIDTH = 6.0
SHIFT_ARROW_TIP_RATIO = 0.14
SHIFT_LABEL_FONT_SIZE = 44.0
SHIFT_LABEL_OUTLINE_WIDTH = 5.0

# Storyboard timings (total: 29.0 s)
BASE_FADE_TIME = 1.25
TOP_VIEW_HOLD_TIME = 2.00
CAMERA_TILT_TIME = 4.00
AXES_FADE_TIME = 1.00
AXES_HOLD_TIME = 1.50
MARKER_FADE_TIME = 1.00
MARKER_HOLD_TIME = 0.75
TANGENT_DRAW_TIME = 1.50
TANGENT_HOLD_TIME = 1.50
ANNOTATION_FADE_TIME = 0.75
SHIFT_UP_TIME = 3.50
SHIFTED_HOLD_TIME = 2.00
PARALLEL_FLASH_TIME = 2.00
PARALLEL_HOLD_TIME = 3.50
ANNOTATION_OUT_TIME = 0.75
FINAL_HOLD_TIME = 0.75
FINAL_FADE_TIME = 1.25


def potential(radius: float) -> float:
    """Return U(r) = -K/r on the cut-off domain."""
    return -K / radius


def radius_at_potential(value: float) -> float:
    """Return the radius of the circular equipotential U(r) = value."""
    return -K / value


def project(points: np.ndarray) -> np.ndarray:
    """Project world points onto the final camera's screen plane."""
    return FINAL_CAMERA_ZOOM * (np.asarray(points) @ SCREEN_BASIS)


def funnel_mouth_outline() -> np.ndarray:
    """Return the mouth's screen-space ellipse relative to the well's U = 0 axis point.

    The widest ring is what the display axes are meant to graze; the stem and the
    source below it are free to cross the lower axis.  Sampled finely in angle,
    since the tangency solved below is only as tight as this outline.
    """
    radius = X_UNIT_LENGTH * radius_at_potential(SURFACE_U_MAX)
    angles = np.linspace(THETA_MIN, THETA_MAX, MOUTH_OUTLINE_SAMPLES)
    mouth = np.stack(
        (
            radius * np.cos(angles),
            radius * np.sin(angles),
            np.full_like(angles, Z_UNIT_LENGTH * SURFACE_U_MAX),
        ),
        axis=-1,
    )
    return project(mouth)


def tangent_wedge_offset(
    outline: np.ndarray,
    upper_slope: float,
    lower_slope: float,
) -> np.ndarray:
    """Return the apex of the wedge of the given slopes that grazes the outline.

    The upper edge is the highest line of its slope with the outline still below it,
    the lower edge the lowest with the outline above it; their crossing is the apex.
    """
    upper_intercept = np.max(outline[:, 1] - upper_slope * outline[:, 0])
    lower_intercept = np.min(outline[:, 1] - lower_slope * outline[:, 0])
    apex_x = (lower_intercept - upper_intercept) / (upper_slope - lower_slope)
    return np.array((apex_x, upper_intercept + upper_slope * apex_x))


# Derived layout.  The well keeps its own origin at the world origin, so placing it
# on screen is entirely the camera's job: shifting the frame centre by the tangency
# offset is what makes both oblique display axes touch the *unshifted* well's mouth.
MOUTH_OUTLINE = funnel_mouth_outline()
FUNNEL_WEDGE_OFFSET = tangent_wedge_offset(
    MOUTH_OUTLINE,
    DISPLAY_UPPER_AXIS_SLOPE,
    DISPLAY_LOWER_AXIS_SLOPE,
)
FUNNEL_SCREEN_POSITION = DISPLAY_AXES_SCREEN_ORIGIN[:2] - FUNNEL_WEDGE_OFFSET
FINAL_FRAME_CENTER = -(
    FUNNEL_SCREEN_POSITION[0] * CAMERA_RIGHT
    + FUNNEL_SCREEN_POSITION[1] * CAMERA_UP
) / FINAL_CAMERA_ZOOM
SHIFT_ARROW_SCREEN_OFFSET = (
    FUNNEL_SCREEN_POSITION[0]
    + np.max(MOUTH_OUTLINE[:, 0])
    + SHIFT_ARROW_SCREEN_GAP
    - DISPLAY_AXES_SCREEN_ORIGIN[0]
)


def make_geometry_axes() -> ThreeDAxes:
    """Build the invisible coordinate system used for all physical geometry."""
    return ThreeDAxes(
        x_range=X_RANGE,
        y_range=Y_RANGE,
        z_range=Z_RANGE,
        x_length=X_LENGTH,
        y_length=Y_LENGTH,
        z_length=Z_LENGTH,
        axis_config={
            "include_ticks": False,
            "include_tip": False,
        },
    )


def make_surface(axes: ThreeDAxes) -> Surface:
    """Build a wireframe whose circular rings are equally spaced in U."""

    def point_at(energy: float, theta: float) -> np.ndarray:
        radius = radius_at_potential(energy)
        return axes.c2p(
            radius * np.cos(theta),
            radius * np.sin(theta),
            energy,
        )

    return Surface(
        point_at,
        u_range=(SURFACE_U_MIN, SURFACE_U_MAX),
        v_range=(THETA_MIN, THETA_MAX),
        resolution=SURFACE_RESOLUTION,
        checkerboard_colors=False,
        fill_opacity=0.0,
        stroke_color=BASE_MESH_COLOR,
        stroke_width=MESH_STROKE_WIDTH,
    ).set_stroke(opacity=MESH_STROKE_OPACITY)


def make_glowing_sphere(
    point: np.ndarray,
    *,
    color: str,
    radius: float,
    glow_radius: float,
    glow_opacity: float,
) -> VGroup:
    """Make a solid marker with a restrained halo for projector visibility."""
    glow = Sphere(
        center=point,
        radius=glow_radius,
        resolution=MARKER_RESOLUTION,
        checkerboard_colors=False,
        fill_color=color,
        fill_opacity=glow_opacity,
        stroke_width=0.0,
    )
    core = Sphere(
        center=point,
        radius=radius,
        resolution=MARKER_RESOLUTION,
        checkerboard_colors=False,
        fill_color=color,
        fill_opacity=1.0,
        stroke_width=0.0,
    )
    return VGroup(glow, core)


def make_radial_tangent(axes: ThreeDAxes) -> Line:
    """Return the radial tangent through P0 using the analytic gradient."""
    radius_0 = np.hypot(X0, Y0)
    radial_direction = np.array([X0, Y0]) / radius_0
    gradient = K * np.array([X0, Y0]) / radius_0**3
    horizontal_delta = TANGENT_HALF_SPAN * radial_direction
    slope_delta = float(np.dot(gradient, horizontal_delta))
    potential_0 = potential(radius_0)

    start = axes.c2p(
        X0 - horizontal_delta[0],
        Y0 - horizontal_delta[1],
        potential_0 - slope_delta,
    )
    end = axes.c2p(
        X0 + horizontal_delta[0],
        Y0 + horizontal_delta[1],
        potential_0 + slope_delta,
    )
    return Line(
        start,
        end,
        color=TANGENT_COLOR,
        stroke_width=TANGENT_STROKE_WIDTH,
        stroke_opacity=TANGENT_OPACITY,
    )


def display_u_point(value: float) -> np.ndarray:
    """Map a potential value to the fixed-frame reference scale."""
    return (
        DISPLAY_AXES_SCREEN_ORIGIN
        + np.array((0.0, value * DISPLAY_U_UNIT_LENGTH, 0.0))
    )


def make_display_axes() -> VGroup:
    """Build a fixed-frame triad matching the reference projection."""
    origin = display_u_point(0.0)
    upper_direction = np.array((1.0, DISPLAY_UPPER_AXIS_SLOPE, 0.0))
    lower_direction = np.array((1.0, DISPLAY_LOWER_AXIS_SLOPE, 0.0))
    upper_direction /= np.linalg.norm(upper_direction)
    lower_direction /= np.linalg.norm(lower_direction)

    visible_upper_axis = Line(
        origin - DISPLAY_XY_NEGATIVE_SPAN * upper_direction,
        origin + DISPLAY_XY_POSITIVE_SPAN * upper_direction,
        color=XY_AXIS_COLOR,
        stroke_width=DISPLAY_AXIS_STROKE_WIDTH,
        stroke_opacity=DISPLAY_XY_OPACITY,
    )
    visible_lower_axis = Line(
        origin - DISPLAY_XY_NEGATIVE_SPAN * lower_direction,
        origin + DISPLAY_XY_POSITIVE_SPAN * lower_direction,
        color=XY_AXIS_COLOR,
        stroke_width=DISPLAY_AXIS_STROKE_WIDTH,
        stroke_opacity=DISPLAY_XY_OPACITY,
    )
    visible_u_axis = Line(
        display_u_point(Z_RANGE[0]),
        display_u_point(Z_RANGE[1]),
        color=SCALE_COLOR,
        stroke_width=DISPLAY_AXIS_STROKE_WIDTH,
        stroke_opacity=DISPLAY_Z_OPACITY,
    )
    ticks = VGroup(
        *(
            Line(
                display_u_point(value)
                + np.array((-DISPLAY_AXIS_TICK_SIZE, 0.0, 0.0)),
                display_u_point(value)
                + np.array((DISPLAY_AXIS_TICK_SIZE, 0.0, 0.0)),
                color=SCALE_COLOR,
                stroke_width=DISPLAY_AXIS_STROKE_WIDTH,
                stroke_opacity=DISPLAY_Z_OPACITY,
            )
            for value in np.arange(Z_RANGE[0], Z_RANGE[1] + 0.5 * Z_RANGE[2], Z_RANGE[2])
        ),
    )
    return VGroup(
        visible_upper_axis,
        visible_lower_axis,
        visible_u_axis,
        ticks,
    )


def make_display_axis_labels() -> VGroup:
    """Place sparse labels beside the fixed-frame U scale."""
    labels = VGroup()
    for value in DISPLAY_AXIS_LABEL_VALUES:
        text = f"{int(value):+d}" if value > 0 else f"{int(value)}"
        label = MathTex(
            text,
            color=SCALE_COLOR,
            font_size=DISPLAY_AXIS_LABEL_FONT_SIZE,
        )
        label.move_to(
            display_u_point(value)
            + np.array((-DISPLAY_AXIS_LABEL_OFFSET, 0.0, 0.0)),
        )
        label.set_stroke(
            color=BACKGROUND_COLOR,
            width=4.0,
            background=True,
        )
        labels.add(label)

    axis_name = MathTex(
        "U",
        color=SCALE_COLOR,
        font_size=DISPLAY_AXIS_LABEL_FONT_SIZE + 2.0,
    )
    axis_name.move_to(
        display_u_point(Z_RANGE[1])
        + np.array(
            (-DISPLAY_AXIS_LABEL_OFFSET, DISPLAY_AXIS_NAME_OFFSET, 0.0),
        ),
    )
    axis_name.set_stroke(
        color=BACKGROUND_COLOR,
        width=4.0,
        background=True,
    )
    labels.add(axis_name)
    return labels


def make_shift_annotation(
    potential_0: float,
) -> tuple[Arrow, MathTex]:
    """Build a fixed-frame +10 arrow beside the displayed U scale."""
    arrow_offset = np.array((SHIFT_ARROW_SCREEN_OFFSET, 0.0, 0.0))
    start = display_u_point(potential_0) + arrow_offset
    end = display_u_point(potential_0 + CONSTANT_SHIFT) + arrow_offset
    arrow = Arrow(
        start,
        end,
        buff=0.0,
        stroke_width=SHIFT_ARROW_STROKE_WIDTH,
        max_tip_length_to_length_ratio=SHIFT_ARROW_TIP_RATIO,
        color=SHIFT_COLOR,
    )
    label = MathTex(
        "+10",
        color=SHIFT_COLOR,
        font_size=SHIFT_LABEL_FONT_SIZE,
    ).move_to(
        0.5 * (start + end)
        + np.array((SHIFT_LABEL_SCREEN_OFFSET, 0.0, 0.0)),
    )
    label.set_stroke(
        color=BACKGROUND_COLOR,
        width=SHIFT_LABEL_OUTLINE_WIDTH,
        background=True,
    )
    return arrow, label


class ConstantShiftScene(ThreeDScene):
    """Show that U and U + c have identical slopes at the same (x, y)."""

    def construct(self) -> None:
        # Everything solid with the well is built from these axes, which stay at the
        # world origin: the final frame centre is what places the well on screen.
        geometry_axes = make_geometry_axes()
        base_surface = make_surface(geometry_axes)
        source = make_glowing_sphere(
            geometry_axes.c2p(0.0, 0.0, SOURCE_Z),
            color=SOURCE_COLOR,
            radius=SOURCE_RADIUS,
            glow_radius=SOURCE_GLOW_RADIUS,
            glow_opacity=SOURCE_GLOW_OPACITY,
        )

        self.set_camera_orientation(
            phi=TOP_CAMERA_PHI,
            theta=CAMERA_THETA,
            zoom=TOP_CAMERA_ZOOM,
            focal_distance=CAMERA_FOCAL_DISTANCE,
            frame_center=np.zeros(3),
        )

        # Beat 1: establish the unlabelled equipotential rings from above.
        self.play(
            FadeIn(base_surface),
            FadeIn(source),
            run_time=BASE_FADE_TIME,
        )
        self.wait(TOP_VIEW_HOLD_TIME)

        # Beat 2: tilt smoothly to reveal the funnel without an azimuthal spin.
        self.move_camera(
            phi=FINAL_CAMERA_PHI,
            theta=CAMERA_THETA,
            zoom=FINAL_CAMERA_ZOOM,
            focal_distance=CAMERA_FOCAL_DISTANCE,
            frame_center=FINAL_FRAME_CENTER,
            run_time=CAMERA_TILT_TIME,
            rate_func=smooth,
        )
        # Manim removes the animated frame-center tracker after move_camera;
        # reassert the final value so subsequent fixed-frame overlays share the
        # exact composition reached at the end of the tilt.
        self.set_camera_orientation(frame_center=FINAL_FRAME_CENTER)

        # Beat 3: introduce a screen-stable reference triad beside the funnel.
        display_axes = make_display_axes()
        display_axis_labels = make_display_axis_labels()
        self.add_fixed_in_frame_mobjects(display_axes, display_axis_labels)
        self.play(
            FadeIn(display_axes),
            FadeIn(display_axis_labels),
            run_time=AXES_FADE_TIME,
        )
        self.wait(AXES_HOLD_TIME)

        # Beat 4: mark the sampled value and draw its analytic radial tangent.
        radius_0 = np.hypot(X0, Y0)
        marker_point = geometry_axes.c2p(X0, Y0, potential(radius_0))
        base_marker = make_glowing_sphere(
            marker_point,
            color=TANGENT_COLOR,
            radius=SAMPLE_RADIUS,
            glow_radius=SAMPLE_GLOW_RADIUS,
            glow_opacity=SAMPLE_GLOW_OPACITY,
        )
        self.play(FadeIn(base_marker), run_time=MARKER_FADE_TIME)
        self.wait(MARKER_HOLD_TIME)

        base_tangent = make_radial_tangent(geometry_axes)
        self.play(Create(base_tangent), run_time=TANGENT_DRAW_TIME)
        self.wait(TANGENT_HOLD_TIME)

        # Beat 5: annotate the constant, then reveal the translating copy in motion.
        potential_0 = potential(radius_0)
        shift_arrow, shift_label = make_shift_annotation(potential_0)
        self.add_fixed_in_frame_mobjects(shift_arrow, shift_label)
        self.play(
            FadeIn(shift_arrow),
            FadeIn(shift_label),
            run_time=ANNOTATION_FADE_TIME,
        )

        shift_vector = geometry_axes.c2p(0.0, 0.0, CONSTANT_SHIFT) - geometry_axes.c2p(
            0.0,
            0.0,
            0.0,
        )
        shifted_surface = base_surface.copy()
        shifted_source = source.copy()
        shifted_marker = base_marker.copy()
        shifted_tangent = base_tangent.copy()
        shifted_group = VGroup(
            shifted_surface,
            shifted_source,
            shifted_marker,
            shifted_tangent,
        )

        self.add(shifted_group)
        self.play(
            shifted_group.animate.shift(shift_vector),
            base_surface.animate.set_stroke(opacity=GHOST_MESH_STROKE_OPACITY),
            source.animate.fade(GHOST_SOURCE_FADE),
            run_time=SHIFT_UP_TIME,
            rate_func=smooth,
        )
        self.wait(SHIFTED_HOLD_TIME)

        # Beat 6: identical sweeps accent the parallel, equal-slope tangents.
        base_flash = base_tangent.copy().set_stroke(
            color=PARALLEL_FLASH_COLOR,
            width=TANGENT_FLASH_WIDTH,
            opacity=1.0,
        )
        shifted_flash = shifted_tangent.copy().set_stroke(
            color=PARALLEL_FLASH_COLOR,
            width=TANGENT_FLASH_WIDTH,
            opacity=1.0,
        )
        self.play(
            ShowPassingFlash(base_flash, time_width=FLASH_TIME_WIDTH),
            ShowPassingFlash(shifted_flash, time_width=FLASH_TIME_WIDTH),
            run_time=PARALLEL_FLASH_TIME,
        )
        self.wait(PARALLEL_HOLD_TIME)

        # Beat 7: finish on the comparison, then clear the frame quickly.
        self.play(
            FadeOut(shift_arrow),
            FadeOut(shift_label),
            run_time=ANNOTATION_OUT_TIME,
        )
        self.remove_fixed_in_frame_mobjects(shift_arrow, shift_label)
        self.remove(shift_arrow, shift_label)
        self.wait(FINAL_HOLD_TIME)

        self.play(
            FadeOut(display_axes),
            FadeOut(display_axis_labels),
            FadeOut(base_surface),
            FadeOut(source),
            FadeOut(base_marker),
            FadeOut(base_tangent),
            FadeOut(shifted_group),
            run_time=FINAL_FADE_TIME,
        )
        self.remove_fixed_in_frame_mobjects(display_axes, display_axis_labels)
        self.remove(display_axes, display_axis_labels)
