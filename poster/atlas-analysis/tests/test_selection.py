from pathlib import Path

import awkward as ak
import numpy as np
import uproot
from uproot.source.file import MemmapSource

from atlas_analysis.selection import (
    BranchMap,
    CutFlow,
    build_initial_masks,
    choose_tree,
    count_true,
    discover_root_files,
    open_root_file,
    select_event_electron,
)


def _selection_sample() -> ak.Array:
    return ak.Array(
        {
            "lep_n": [2, 1, 1, 0],
            "lep_type": [[13, 11], [11], [-11], []],
            "lep_pt": [[60_000.0, 40_000.0], [24_000.0], [35_000.0], []],
            "lep_eta": [[0.3, 0.2], [0.1], [1.45], []],
            "lep_isTightID": [[1, 1], [1], [1], []],
            "lep_ptcone30": [[1_000.0, 2_000.0], [500.0], [1_000.0], []],
            "met_et": [40_000.0, 40_000.0, 40_000.0, 40_000.0],
        }
    )


def test_highest_pt_electron_keeps_associated_fields() -> None:
    branches = BranchMap()
    arrays = _selection_sample()
    electron = select_event_electron(arrays, branches)

    assert ak.to_list(electron.count) == [1, 1, 1, 0]
    assert ak.to_list(electron.pt_raw) == [40_000.0, 24_000.0, 35_000.0, None]
    assert ak.to_list(electron.eta) == [0.2, 0.1, 1.45, None]
    assert ak.to_list(electron.ptcone30_raw) == [2_000.0, 500.0, 1_000.0, None]


def test_cut_masks_preserve_abcd_selection_semantics() -> None:
    branches = BranchMap()
    arrays = _selection_sample()
    electron = select_event_electron(arrays, branches)
    masks = build_initial_masks(arrays, branches, electron, 30.0, 0.15)

    assert [count_true(mask) for mask in masks.values()] == [3, 3, 2, 2, 1, 1, 1]


def test_cutflow_efficiencies() -> None:
    cutflow = CutFlow(("All", "First", "Second"))
    cutflow.add_count("All", 100)
    cutflow.add_count("First", 50)
    cutflow.add_count("Second", 10)
    rows = cutflow.results()
    assert rows[1].step_efficiency == 0.5
    assert rows[2].step_efficiency == 0.2
    assert rows[2].total_efficiency == 0.1


def test_root_discovery_and_tree_selection(tmp_path: Path) -> None:
    root_path = tmp_path / "sample.root"
    with uproot.recreate(root_path) as root_file:
        root_file.mktree("mini", {"value": "int32"})
        root_file["mini"].extend(
            {"value": np.array([1, 2, 3], dtype=np.int32)}
        )

    assert discover_root_files(tmp_path, None) == [root_path.resolve()]
    with open_root_file(root_path) as root_file:
        assert isinstance(root_file.file.source, MemmapSource)
        assert choose_tree(root_file, None) == "mini"
        assert choose_tree(root_file, "mini") == "mini"
