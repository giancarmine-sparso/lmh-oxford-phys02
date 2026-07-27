"""A constant vertical shift changes potential values, but not their gradient."""

from __future__ import annotations

import numpy as np

from manim import (
    DEGREES,
    LEFT,
    PI,
    AnimationGroup,
    Arrow3D,
    Create,
    FadeIn,
    FadeOut,
    GREY_C,
    Integer,
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
    linear,
)


# Visual theme
BACKGROUND_COLOR = "#090D18"
BASE_MESH_COLOR = GREY_C
AXIS_COLOR = WHITE
TANGENT_COLOR = "#FF70B7"
PARALLEL_FLASH_COLOR = "#FFF0F8"
MARKER_COLOR = "#FFD166"
SHIFT_COLOR = "#67D4FF"

config.background_color = BACKGROUND_COLOR

# Potential and sample point
K = 8.0
CONSTANT_SHIFT = 10.0
R_MIN = 0.45
R_MAX = 4.0
THETA_MIN = 0.0
THETA_MAX = 2.0 * PI
X0 = 1.6
Y0 = 0.0

# Axes and surface geometry
X_RANGE = (-4.5, 4.5, 1.0)
Y_RANGE = (-4.5, 4.5, 1.0)
Z_RANGE = (-25.0, 12.0, 5.0)
X_LENGTH = 6.7
Y_LENGTH = 6.7
Z_LENGTH = 6.3
AXIS_STROKE_WIDTH = 2.25
AXIS_TICK_SIZE = 0.055
AXIS_NUMBER_FONT_SIZE = 18.0
Z_NUMBER_OFFSET = 0.30
Z_NUMBERS = (-20.0, -15.0, -10.0, -5.0, 5.0, 10.0)
XY_AXIS_OPACITY = 0.80
Z_AXIS_OPACITY = 1.00
SURFACE_RESOLUTION = (4, 8)
MESH_STROKE_WIDTH = 0.65
MESH_STROKE_OPACITY = 0.45

# Marker and tangent geometry
MARKER_RADIUS = 0.12
MARKER_GLOW_RADIUS = 0.20
MARKER_RESOLUTION = (12, 24)
MARKER_FILL_OPACITY = 1.0
MARKER_GLOW_OPACITY = 0.14
TANGENT_HALF_SPAN = 0.80
TANGENT_STROKE_WIDTH = 7.0
TANGENT_OPACITY = 0.92
TANGENT_FLASH_WIDTH = 12.0
FLASH_TIME_WIDTH = 0.35

# Shift annotation
SHIFT_ARROW_THICKNESS = 0.025
SHIFT_ARROW_HEAD_HEIGHT = 0.24
SHIFT_ARROW_HEAD_RADIUS = 0.07
SHIFT_LABEL_FONT_SIZE = 32.0
SHIFT_LABEL_OUTLINE_WIDTH = 4.0
SHIFT_LABEL_SCREEN_POSITION = np.array((-1.45, 0.25, 0.0))

# Camera
CAMERA_PHI = 65.0 * DEGREES
CAMERA_THETA = -50.0 * DEGREES
CAMERA_ZOOM = 1.25

# Storyboard timings (total: 27.75 s)
BASE_FADE_TIME = 2.50
BASE_HOLD_TIME = 1.00
MARKER_FADE_TIME = 1.25
MARKER_HOLD_TIME = 2.00
TANGENT_DRAW_TIME = 2.00
TANGENT_HOLD_TIME = 3.00
COPY_FADE_TIME = 1.50
ANNOTATION_FADE_TIME = 1.00
SHIFT_UP_TIME = 4.00
SHIFTED_HOLD_TIME = 2.00
PARALLEL_FLASH_TIME = 2.00
PARALLEL_HOLD_TIME = 1.50
ANNOTATION_OUT_TIME = 1.00
FINAL_FADE_TIME = 3.00


def potential(radius: float) -> float:
    """Return U(r) = -K/r on the cut-off domain."""
    return -K / radius


def make_surface(axes: ThreeDAxes) -> Surface:
    """Build a polar wireframe so radial lines and circles are explicit."""
    return Surface(
        lambda radius, theta: axes.c2p(
            radius * np.cos(theta),
            radius * np.sin(theta),
            potential(radius),
        ),
        u_range=(R_MIN, R_MAX),
        v_range=(THETA_MIN, THETA_MAX),
        resolution=SURFACE_RESOLUTION,
        checkerboard_colors=False,
        fill_opacity=0.0,
        stroke_color=BASE_MESH_COLOR,
        stroke_width=MESH_STROKE_WIDTH,
    ).set_stroke(opacity=MESH_STROKE_OPACITY)


def make_z_number_labels(axes: ThreeDAxes) -> VGroup:
    """Place legible integer labels beside the static three-dimensional z-axis."""
    labels = VGroup()
    for value in Z_NUMBERS:
        label = Integer(
            int(value),
            color=AXIS_COLOR,
            font_size=AXIS_NUMBER_FONT_SIZE,
        )
        label.move_to(axes.c2p(0.0, 0.0, value) + Z_NUMBER_OFFSET * LEFT)
        labels.add(label)
    return labels


def make_marker(point: np.ndarray) -> VGroup:
    """Make a bright value marker with a subtle, purely visual halo."""
    glow = Sphere(
        center=point,
        radius=MARKER_GLOW_RADIUS,
        resolution=MARKER_RESOLUTION,
        checkerboard_colors=False,
        fill_color=MARKER_COLOR,
        fill_opacity=MARKER_GLOW_OPACITY,
        stroke_width=0.0,
    )
    core = Sphere(
        center=point,
        radius=MARKER_RADIUS,
        resolution=MARKER_RESOLUTION,
        checkerboard_colors=False,
        fill_color=MARKER_COLOR,
        fill_opacity=MARKER_FILL_OPACITY,
        stroke_width=0.0,
    )
    return VGroup(glow, core)


def make_radial_tangent(axes: ThreeDAxes) -> Line:
    """Return the radial tangent line through P0 using the analytic gradient."""
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


class ConstantShiftScene(ThreeDScene):
    """Show that U and U + c have identical slopes at the same (x, y)."""

    def construct(self) -> None:
        axes = ThreeDAxes(
            x_range=X_RANGE,
            y_range=Y_RANGE,
            z_range=Z_RANGE,
            x_length=X_LENGTH,
            y_length=Y_LENGTH,
            z_length=Z_LENGTH,
            axis_config={
                "color": AXIS_COLOR,
                "stroke_width": AXIS_STROKE_WIDTH,
                "include_ticks": True,
                "tick_size": AXIS_TICK_SIZE,
                "include_tip": False,
            },
            z_axis_config={
                "include_numbers": False,
            },
        )
        axes.x_axis.set_stroke(opacity=XY_AXIS_OPACITY)
        axes.y_axis.set_stroke(opacity=XY_AXIS_OPACITY)
        axes.z_axis.set_stroke(opacity=Z_AXIS_OPACITY)
        z_number_labels = make_z_number_labels(axes)
        base_surface = make_surface(axes)

        self.set_camera_orientation(
            phi=CAMERA_PHI,
            theta=CAMERA_THETA,
            zoom=CAMERA_ZOOM,
        )
        z_number_labels.set_opacity(0.0)
        self.add_fixed_orientation_mobjects(*z_number_labels)

        # Beat 1: establish the energy landscape and its numerical z scale.
        self.play(
            AnimationGroup(
                FadeIn(axes),
                FadeIn(base_surface),
                z_number_labels.animate.set_opacity(1.0),
                lag_ratio=0.0,
            ),
            run_time=BASE_FADE_TIME,
        )
        self.wait(BASE_HOLD_TIME)

        # Beat 2: this sphere marks U(x0, y0); it is not a rolling object.
        radius_0 = np.hypot(X0, Y0)
        marker_point = axes.c2p(X0, Y0, potential(radius_0))
        base_marker = make_marker(marker_point)
        self.play(FadeIn(base_marker), run_time=MARKER_FADE_TIME)
        self.wait(MARKER_HOLD_TIME)

        # Beat 3: the line is the radial tangent determined by grad(U) at P0.
        base_tangent = make_radial_tangent(axes)
        self.play(Create(base_tangent), run_time=TANGENT_DRAW_TIME)
        self.wait(TANGENT_HOLD_TIME)

        # Beat 4: duplicate everything, then translate only in the energy axis.
        shifted_surface = base_surface.copy()
        shifted_marker = base_marker.copy()
        shifted_tangent = base_tangent.copy()
        shifted_group = VGroup(
            shifted_surface,
            shifted_marker,
            shifted_tangent,
        )
        shift_vector = axes.c2p(0.0, 0.0, CONSTANT_SHIFT) - axes.c2p(
            0.0,
            0.0,
            0.0,
        )

        self.play(FadeIn(shifted_group), run_time=COPY_FADE_TIME)

        potential_0 = potential(radius_0)
        shift_arrow = Arrow3D(
            start=axes.c2p(0.0, 0.0, potential_0),
            end=axes.c2p(0.0, 0.0, potential_0 + CONSTANT_SHIFT),
            thickness=SHIFT_ARROW_THICKNESS,
            height=SHIFT_ARROW_HEAD_HEIGHT,
            base_radius=SHIFT_ARROW_HEAD_RADIUS,
            color=SHIFT_COLOR,
        )
        shift_label = MathTex(
            "+10",
            color=SHIFT_COLOR,
            font_size=SHIFT_LABEL_FONT_SIZE,
        ).move_to(SHIFT_LABEL_SCREEN_POSITION)
        shift_label.set_stroke(
            color=BACKGROUND_COLOR,
            width=SHIFT_LABEL_OUTLINE_WIDTH,
            background=True,
        )
        self.add_fixed_in_frame_mobjects(shift_label)
        self.play(
            FadeIn(shift_arrow),
            FadeIn(shift_label),
            run_time=ANNOTATION_FADE_TIME,
        )
        self.play(
            shifted_group.animate.shift(shift_vector),
            run_time=SHIFT_UP_TIME,
            rate_func=linear,
        )
        self.wait(SHIFTED_HOLD_TIME)

        # Beat 5: identical sweeps accent the parallel, equal-slope tangents.
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

        # Beat 6: end on the shifted comparison without undoing c.
        self.play(
            FadeOut(shift_arrow),
            FadeOut(shift_label),
            run_time=ANNOTATION_OUT_TIME,
        )
        self.remove_fixed_in_frame_mobjects(shift_label)
        self.play(
            FadeOut(axes),
            FadeOut(z_number_labels),
            FadeOut(base_surface),
            FadeOut(base_marker),
            FadeOut(base_tangent),
            FadeOut(shifted_group),
            run_time=FINAL_FADE_TIME,
        )
        self.remove_fixed_orientation_mobjects(*z_number_labels)
