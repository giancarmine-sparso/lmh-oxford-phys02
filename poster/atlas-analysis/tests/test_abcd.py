from pathlib import Path

from matplotlib.colors import LogNorm
from matplotlib.offsetbox import AnnotationBbox
import numpy as np
import pytest

import atlas_analysis.abcd as abcd_module
from atlas_analysis.abcd import (
    ABCDBoundaries,
    _format_compact_count,
    _histogram2d_for_display,
    _prepare_heatmap,
    build_region_masks,
    estimate_abcd,
    plot_abcd_plane,
    summarize_region_assignment,
)


BOUNDARIES = ABCDBoundaries(
    iso_signal_max=0.10,
    iso_control_min=0.20,
    x_control_max=25.0,
    x_signal_min=30.0,
)


def test_balanced_regions_and_prediction() -> None:
    isolation = np.array([0.02, 0.04, 0.25, 0.30, 0.03, 0.05, 0.22, 0.35])
    met_gev = np.array([45.0, 60.0, 50.0, 70.0, 10.0, 20.0, 15.0, 25.0])

    masks = build_region_masks(isolation, met_gev, BOUNDARIES)
    assert {name: int(mask.sum()) for name, mask in masks.items()} == {
        "A": 2,
        "B": 2,
        "C": 2,
        "D": 2,
    }
    result = estimate_abcd(isolation, met_gev, BOUNDARIES)
    assert result.predicted_a == pytest.approx(2.0)
    assert result.predicted_a_uncertainty == pytest.approx(np.sqrt(6.0))


def test_gaps_boundaries_and_nonfinite_values_are_reported() -> None:
    isolation = np.array([0.05, 0.25, 0.05, 0.25, 0.15, 0.05, np.nan])
    met_gev = np.array([40.0, 40.0, 10.0, 10.0, 40.0, 27.0, 40.0])

    summary = summarize_region_assignment(isolation, met_gev, BOUNDARIES)
    assert "  A: 1 events" in summary
    assert "  B: 1 events" in summary
    assert "  C: 1 events" in summary
    assert "  D: 1 events" in summary
    assert "  excluded by gap: 2 events" in summary
    assert "  invalid/non-finite: 1 events" in summary
    assert "  gap fraction: 33.33%" in summary


def test_weighted_prediction_and_zero_control_region() -> None:
    isolation = np.array([0.05, 0.25, 0.05, 0.25])
    met_gev = np.array([40.0, 40.0, 10.0, 10.0])
    result = estimate_abcd(
        isolation,
        met_gev,
        BOUNDARIES,
        weights=np.array([1.0, 2.0, 3.0, 4.0]),
    )
    assert result.predicted_a == pytest.approx(1.5)

    with pytest.raises(ZeroDivisionError):
        estimate_abcd(
            isolation[:3],
            met_gev[:3],
            BOUNDARIES,
        )


def test_invalid_boundaries_are_rejected() -> None:
    with pytest.raises(ValueError):
        ABCDBoundaries(0.20, 0.10, 25.0, 30.0)
    with pytest.raises(ValueError):
        ABCDBoundaries(0.10, 0.20, 30.0, 25.0)


def test_display_histogram_folds_upper_overflow_without_double_counting() -> None:
    met_gev = np.array([20.0, 120.0, 20.0, 120.0])
    isolation = np.array([0.05, 0.05, 0.70, 0.70])
    weights = np.array([1.0, 2.0, 3.0, 5.0])
    original_met = met_gev.copy()
    original_isolation = isolation.copy()

    histogram, x_edges, y_edges = _histogram2d_for_display(
        met_gev,
        isolation,
        bins=(2, 2),
        x_range=(0.0, 100.0),
        isolation_range=(0.0, 0.50),
        weights=weights,
    )

    np.testing.assert_array_equal(met_gev, original_met)
    np.testing.assert_array_equal(isolation, original_isolation)
    np.testing.assert_allclose(x_edges, [0.0, 50.0, 100.0])
    np.testing.assert_allclose(y_edges, [0.0, 0.25, 0.50])
    np.testing.assert_allclose(histogram, [[1.0, 3.0], [2.0, 5.0]])
    assert histogram.sum() == pytest.approx(weights.sum())


def test_log_heatmap_masks_empty_bins_with_dark_magma_color() -> None:
    histogram = np.array([[0.0, 1.0], [4.0, -2.0]])

    masked, cmap, norm, dark_color = _prepare_heatmap(
        histogram, logarithmic=True
    )

    assert isinstance(norm, LogNorm)
    np.testing.assert_array_equal(
        np.ma.getmaskarray(masked), [[True, False], [False, True]]
    )
    np.testing.assert_allclose(cmap.get_bad(), dark_color)
    np.testing.assert_allclose(cmap.get_under(), dark_color)
    rendered = cmap(norm(masked))
    np.testing.assert_allclose(rendered[0, 0], dark_color)
    np.testing.assert_allclose(rendered[1, 1], dark_color)


@pytest.mark.parametrize(
    ("count", "expected"),
    [
        (2_112_319, "2.11M"),
        (7_119, "7.12k"),
        (898_022, "898k"),
        (12_171, "12.2k"),
    ],
)
def test_region_counts_use_requested_compact_format(
    count: int, expected: str
) -> None:
    assert _format_compact_count(count) == expected


def test_abcd_plot_contains_required_visual_elements(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    captured: dict[str, object] = {}

    def capture_figure(figure: object, output: str | Path) -> tuple[Path, Path]:
        captured["figure"] = figure
        path = Path(output)
        return path.with_suffix(".png"), path.with_suffix(".pdf")

    monkeypatch.setattr(abcd_module, "save_figure_variants", capture_figure)
    isolation = np.array([0.05, 0.25, 0.05, 0.25, 0.15, 0.70])
    met_gev = np.array([40.0, 40.0, 10.0, 10.0, 27.0, 120.0])

    plot_abcd_plane(
        isolation,
        met_gev,
        BOUNDARIES,
        tmp_path / "captured.png",
        bins=(10, 10),
    )

    figure = captured["figure"]
    axis = figure.axes[0]
    colorbar_axis = figure.axes[1]
    mesh = axis.collections[0]
    dark_color = mesh.cmap(0.0)

    assert isinstance(mesh.norm, LogNorm)
    assert np.any(np.ma.getmaskarray(mesh.get_array()))
    np.testing.assert_allclose(mesh.cmap.get_bad(), dark_color)
    np.testing.assert_allclose(mesh.cmap.get_under(), dark_color)
    np.testing.assert_allclose(axis.get_facecolor(), dark_color)
    assert figure._suptitle.get_text() == "ABCD control regions"
    assert axis.get_title() == "Preliminary data-only background study"
    assert colorbar_axis.get_ylabel() == "Events per bin"
    label_scale = abcd_module.ABCD_POSTER_LABEL_SCALE
    assert figure._suptitle.get_fontsize() == pytest.approx(17 * label_scale)
    assert axis.title.get_fontsize() == pytest.approx(11 * label_scale)
    assert axis.xaxis.label.get_fontsize() == pytest.approx(12 * label_scale)
    assert axis.yaxis.label.get_fontsize() == pytest.approx(12 * label_scale)
    assert colorbar_axis.yaxis.label.get_fontsize() == pytest.approx(
        11 * label_scale
    )
    assert len(axis.lines) == 4
    assert len(axis.patches) == 2
    region_labels = [
        artist for artist in axis.artists if isinstance(artist, AnnotationBbox)
    ]
    assert len(region_labels) == 4
    region_label_parts = region_labels[0].offsetbox.get_children()
    assert region_label_parts[0].get_children()[0].get_fontsize() == pytest.approx(
        15 * label_scale
    )
    assert region_label_parts[1].get_children()[0].get_fontsize() == pytest.approx(
        10 * label_scale
    )
    visible_text = {text.get_text() for text in axis.texts}
    assert "excluded MET gap" in visible_text
    assert "excluded isolation gap" in visible_text


def test_abcd_plot_is_written_as_png_and_pdf(tmp_path: Path) -> None:
    rng = np.random.default_rng(7)
    isolation = np.clip(rng.exponential(0.10, 1_000), 0.0, 0.50)
    met_gev = np.clip(rng.exponential(25.0, 1_000), 0.0, 100.0)
    output = tmp_path / "abcd_plane.png"

    returned = plot_abcd_plane(isolation, met_gev, BOUNDARIES, output)
    assert returned == output
    assert output.is_file()
    assert output.stat().st_size > 0
    assert output.with_suffix(".pdf").stat().st_size > 0
