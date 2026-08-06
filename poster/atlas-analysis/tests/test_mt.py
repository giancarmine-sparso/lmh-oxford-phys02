from pathlib import Path

import awkward as ak
import numpy as np

from atlas_analysis.mt import MtResult, calculate_mt_chunk, plot_mt


def _mt_sample() -> dict[str, ak.Array]:
    return {
        "lep_pt": ak.Array(
            [[30_000.0], [50_000.0, 35_000.0], [24_000.0], [30_000.0],
             [30_000.0], [30_000.0], [30_000.0]]
        ),
        "lep_eta": ak.Array(
            [[0.2], [0.1, 0.2], [0.2], [0.2], [1.45], [0.2], [0.2]]
        ),
        "lep_phi": ak.Array([[0.0], [0.0, 0.0], [0.0], [0.0], [0.0], [0.0], [0.0]]),
        "lep_type": ak.Array([[11], [13, 11], [11], [11], [11], [11], [11]]),
        "lep_isTightID": ak.Array([[1], [1, 1], [1], [1], [1], [1], [1]]),
        "lep_ptcone30": ak.Array(
            [[1_000.0], [1_000.0, 1_000.0], [500.0], [500.0],
             [500.0], [3_000.0], [500.0]]
        ),
        "met_et": ak.Array([40_000.0, 40_000.0, 40_000.0, 40_000.0, 40_000.0, 40_000.0, 30_000.0]),
        "met_phi": ak.Array([1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0]),
        "trigE": ak.Array([True, True, True, False, True, True, True]),
    }


def test_mt_uses_first_lepton_and_strict_legacy_thresholds() -> None:
    chunk = calculate_mt_chunk(_mt_sample())
    assert chunk.broad_events == 6
    assert chunk.enriched_events == 1
    assert int(chunk.broad_histogram.sum()) == 6
    assert int(chunk.enriched_histogram.sum()) == 1


def test_mt_plots_are_written_with_stable_names(tmp_path: Path) -> None:
    bins = np.linspace(0.0, 200.0, 51)
    broad = np.zeros(50, dtype=np.int64)
    enriched = np.zeros(50, dtype=np.int64)
    broad[4] = 10
    enriched[5] = 3
    result = MtResult(bins, broad, enriched, 10, 3)

    raw, normalized = plot_mt(result, tmp_path)
    assert raw == tmp_path / "mt_before_after.png"
    assert normalized == tmp_path / "mt_normalized_comparison.png"
    assert raw.stat().st_size > 0
    assert normalized.stat().st_size > 0
    assert raw.with_suffix(".pdf").stat().st_size > 0
    assert normalized.with_suffix(".pdf").stat().st_size > 0
    for panel_name in ("mt_broad_sample", "mt_selected_sample"):
        panel = tmp_path / f"{panel_name}.png"
        assert panel.stat().st_size > 0
        assert panel.with_suffix(".pdf").stat().st_size > 0
