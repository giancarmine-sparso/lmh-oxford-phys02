"""Shared ROOT I/O, event selection, cut-flow, and diagnostics."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable, Mapping, Sequence

import awkward as ak
import numpy as np
import uproot
from uproot.source.file import MemmapSource


PROJECT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_DATA_DIR = PROJECT_DIR / "data" / "1lep" / "Data"
DEFAULT_DATA_FILE = DEFAULT_DATA_DIR / "data_A.1lep.root"

MEV_TO_GEV = 1.0e-3
DEFAULT_ELECTRON_PT_MIN_GEV = 30.0
DEFAULT_TRACK_ISOLATION_MAX = 0.15

ELECTRON_ABS_ETA_MAX = 2.47
CALORIMETER_TRANSITION_ABS_ETA_MIN = 1.37
CALORIMETER_TRANSITION_ABS_ETA_MAX = 1.52


@dataclass(frozen=True)
class BranchMap:
    """Mapping between analysis concepts and ROOT branch names."""

    lepton_count: str = "lep_n"
    lepton_type: str = "lep_type"
    lepton_pt: str = "lep_pt"
    lepton_eta: str = "lep_eta"
    lepton_is_tight_id: str = "lep_isTightID"
    lepton_ptcone30: str = "lep_ptcone30"
    missing_et: str = "met_et"

    def required(self) -> tuple[str, ...]:
        return (
            self.lepton_count,
            self.lepton_type,
            self.lepton_pt,
            self.lepton_eta,
            self.lepton_is_tight_id,
            self.lepton_ptcone30,
            self.missing_et,
        )


@dataclass(frozen=True)
class CutResult:
    """One row of a cumulative cut-flow table."""

    name: str
    events: int
    step_efficiency: float
    total_efficiency: float


@dataclass
class CutFlow:
    """Accumulate event counts while ROOT files are processed in chunks."""

    selection_order: tuple[str, ...]
    counts: dict[str, int] = field(default_factory=lambda: defaultdict(int))

    def add_count(self, selection: str, events: int) -> None:
        if selection not in self.selection_order:
            raise KeyError(f"Unknown cut-flow selection: {selection}")
        if events < 0:
            raise ValueError("Event count cannot be negative")
        self.counts[selection] += int(events)

    def results(self) -> list[CutResult]:
        total_events = self.counts[self.selection_order[0]]
        previous_events = total_events
        rows: list[CutResult] = []

        for index, name in enumerate(self.selection_order):
            events = self.counts[name]
            if index == 0:
                step_efficiency = 1.0
                total_efficiency = 1.0
            else:
                step_efficiency = events / previous_events if previous_events else 0.0
                total_efficiency = events / total_events if total_events else 0.0

            rows.append(
                CutResult(
                    name=name,
                    events=events,
                    step_efficiency=step_efficiency,
                    total_efficiency=total_efficiency,
                )
            )
            previous_events = events

        return rows

    def print_table(self) -> None:
        rows = self.results()
        name_width = max(len(row.name) for row in rows)
        header = (
            f"{'Selection':<{name_width}}  "
            f"{'Events':>12}  "
            f"{'Step eff.':>10}  "
            f"{'Total eff.':>11}"
        )

        print("\nCUT-FLOW — PHASE 1")
        print(header)
        print("-" * len(header))
        for row in rows:
            print(
                f"{row.name:<{name_width}}  "
                f"{row.events:>12,d}  "
                f"{row.step_efficiency:>9.2%}  "
                f"{row.total_efficiency:>10.2%}"
            )


def discover_root_files(input_path: Path, max_files: int | None) -> list[Path]:
    """Return ROOT files from either a file path or a directory."""

    resolved_path = input_path.expanduser().resolve()
    if resolved_path.is_file():
        if resolved_path.suffix.lower() != ".root":
            raise ValueError(f"Input file is not a ROOT file: {resolved_path}")
        files = [resolved_path]
    elif resolved_path.is_dir():
        files = sorted(resolved_path.rglob("*.root"))
    else:
        raise FileNotFoundError(f"Input path does not exist: {resolved_path}")

    if not files:
        raise FileNotFoundError(f"No ROOT files found under: {resolved_path}")

    if max_files is not None:
        if max_files <= 0:
            raise ValueError("max_files must be positive or omitted")
        files = files[:max_files]

    return files


def open_root_file(file_path: str | Path) -> uproot.ReadOnlyDirectory:
    """Open a local ROOT file without the fsspec worker used by default."""

    return uproot.open(file_path, handler=MemmapSource)


def choose_tree(root_file: uproot.ReadOnlyDirectory, requested: str | None) -> str:
    """Choose a TTree, preferring an explicit name and then ``mini``."""

    classnames = root_file.classnames(recursive=False)
    tree_names = [
        key.split(";")[0]
        for key, class_name in classnames.items()
        if class_name.startswith("TTree")
    ]

    if requested is not None:
        if requested not in tree_names:
            available = ", ".join(tree_names) or "none"
            raise KeyError(
                f"Tree '{requested}' not found. Available TTrees: {available}"
            )
        return requested

    if "mini" in tree_names:
        return "mini"
    if len(tree_names) == 1:
        return tree_names[0]

    available = ", ".join(tree_names) or "none"
    raise RuntimeError(
        "Could not choose the analysis tree automatically. "
        f"Available TTrees: {available}. Pass --tree explicitly."
    )


def matching_branches(
    branch_names: Iterable[str], keywords: Sequence[str]
) -> list[str]:
    """Return branch names containing at least one keyword."""

    lowered_keywords = tuple(keyword.lower() for keyword in keywords)
    return sorted(
        name
        for name in branch_names
        if any(keyword in name.lower() for keyword in lowered_keywords)
    )


def print_branch_group(title: str, branches: Sequence[str]) -> None:
    print(f"\n{title} ({len(branches)})")
    print("-" * (len(title) + len(str(len(branches))) + 3))
    if not branches:
        print("  No matching branches found")
        return
    for branch in branches:
        print(f"  {branch}")


def inspect_file(
    file_path: Path,
    requested_tree: str | None,
    branches: BranchMap,
) -> tuple[str, int]:
    """Inspect one ROOT file and validate the branch mapping."""

    print(f"\nOpening: {file_path}")
    with open_root_file(file_path) as root_file:
        print("\nTop-level objects:")
        for key in root_file.keys():
            print(f"  {key}")

        tree_name = choose_tree(root_file, requested_tree)
        tree = root_file[tree_name]
        branch_names = list(tree.keys())
        event_count = int(tree.num_entries)

        print(f"\nSelected tree: {tree_name}")
        print(f"Events in tree: {event_count:,}")
        print(f"Total branches: {len(branch_names)}")

        missing = sorted(set(branches.required()) - set(branch_names))
        if missing:
            raise KeyError(
                "Required branches are missing from the tree: " + ", ".join(missing)
            )

        groups = {
            "Electron/lepton candidates": ("electron", "el_", "lep_", "lepton"),
            "Isolation candidates": ("iso", "cone", "ptcone", "etcone"),
            "Missing-momentum candidates": ("met", "missing", "etmiss"),
            "Identification candidates": ("tight", "medium", "loose", "id"),
            "Trigger candidates": ("trig", "trigger"),
        }
        for title, keywords in groups.items():
            print_branch_group(title, matching_branches(branch_names, keywords))

        print("\nValidated branch mapping")
        print(f"  lepton count     : {branches.lepton_count}")
        print(f"  lepton type      : {branches.lepton_type}")
        print(f"  lepton pT        : {branches.lepton_pt}")
        print(f"  lepton eta       : {branches.lepton_eta}")
        print(f"  lepton tight ID  : {branches.lepton_is_tight_id}")
        print(f"  lepton ptcone30  : {branches.lepton_ptcone30}")
        print(f"  missing ET       : {branches.missing_et}")

    return tree_name, event_count


def count_true(mask: ak.Array) -> int:
    """Count selected events after replacing missing booleans with False."""

    return int(ak.sum(ak.fill_none(mask, False)))


def first_item(array: ak.Array) -> np.ndarray:
    """Extract the first value from each event-level jagged array."""

    return ak.to_numpy(ak.firsts(array))


@dataclass(frozen=True)
class SelectedElectron:
    """Electron information reduced to one candidate per event."""

    count: ak.Array
    has_candidate: ak.Array
    pt_raw: ak.Array
    pt_gev: ak.Array
    eta: ak.Array
    is_tight_id: ak.Array
    ptcone30_raw: ak.Array
    relative_track_isolation: ak.Array


def select_event_electron(arrays: ak.Array, branches: BranchMap) -> SelectedElectron:
    """Select the highest-pT electron candidate in every event."""

    is_electron = np.abs(arrays[branches.lepton_type]) == 11
    electron_count = ak.sum(is_electron, axis=1)

    electron_pts = arrays[branches.lepton_pt][is_electron]
    descending_pt_order = ak.argsort(electron_pts, axis=1, ascending=False)

    selected_pt_raw = ak.firsts(electron_pts[descending_pt_order])
    selected_eta = ak.firsts(
        arrays[branches.lepton_eta][is_electron][descending_pt_order]
    )
    selected_tight_id = ak.firsts(
        arrays[branches.lepton_is_tight_id][is_electron][descending_pt_order]
    )
    selected_ptcone30 = ak.firsts(
        arrays[branches.lepton_ptcone30][is_electron][descending_pt_order]
    )

    return SelectedElectron(
        count=electron_count,
        has_candidate=electron_count >= 1,
        pt_raw=selected_pt_raw,
        pt_gev=selected_pt_raw * MEV_TO_GEV,
        eta=selected_eta,
        is_tight_id=selected_tight_id,
        ptcone30_raw=selected_ptcone30,
        relative_track_isolation=selected_ptcone30 / selected_pt_raw,
    )


def electron_pt_selection_name(minimum_gev: float) -> str:
    return f"Selected electron pT >= {minimum_gev:g} GeV"


def eta_coverage_selection_name() -> str:
    return f"Selected electron |eta| < {ELECTRON_ABS_ETA_MAX:g}"


def eta_transition_veto_selection_name() -> str:
    return (
        "Exclude "
        f"{CALORIMETER_TRANSITION_ABS_ETA_MIN:g} < |eta| < "
        f"{CALORIMETER_TRANSITION_ABS_ETA_MAX:g}"
    )


def tight_id_selection_name() -> str:
    return "Selected electron passes tight ID"


def track_isolation_selection_name(maximum: float) -> str:
    return f"Track isolation ptcone30/pT < {maximum:g}"


def build_initial_masks(
    arrays: ak.Array,
    branches: BranchMap,
    electron: SelectedElectron,
    electron_pt_min_gev: float,
    track_isolation_max: float,
) -> dict[str, ak.Array]:
    """Build cumulative masks through the track-isolation requirement."""

    has_lepton = arrays[branches.lepton_count] >= 1
    has_electron = has_lepton & electron.has_candidate
    passes_electron_pt = has_electron & (electron.pt_gev >= electron_pt_min_gev)

    abs_eta = np.abs(electron.eta)
    passes_eta_coverage = passes_electron_pt & (abs_eta < ELECTRON_ABS_ETA_MAX)
    is_in_transition_region = (
        (abs_eta > CALORIMETER_TRANSITION_ABS_ETA_MIN)
        & (abs_eta < CALORIMETER_TRANSITION_ABS_ETA_MAX)
    )
    passes_transition_veto = passes_eta_coverage & ~is_in_transition_region
    passes_tight_id = passes_transition_veto & (electron.is_tight_id == 1)
    passes_track_isolation = (
        passes_tight_id
        & np.isfinite(electron.relative_track_isolation)
        & (electron.relative_track_isolation < track_isolation_max)
    )

    return {
        "At least one reconstructed lepton": has_lepton,
        "At least one electron candidate": has_electron,
        electron_pt_selection_name(electron_pt_min_gev): passes_electron_pt,
        eta_coverage_selection_name(): passes_eta_coverage,
        eta_transition_veto_selection_name(): passes_transition_veto,
        tight_id_selection_name(): passes_tight_id,
        track_isolation_selection_name(
            track_isolation_max
        ): passes_track_isolation,
    }


@dataclass
class TrackIsolationDiagnostics:
    """Streaming diagnostic for ptcone30 / electron pT after tight ID."""

    sample_limit: int = 200_000
    baseline_events: int = 0
    finite_values: int = 0
    nonfinite_values: int = 0
    negative_values: int = 0
    minimum: float = float("inf")
    maximum: float = float("-inf")
    sampled_values: list[np.ndarray] = field(default_factory=list)
    sampled_count: int = 0

    def update(self, relative_isolation: ak.Array, baseline_mask: ak.Array) -> None:
        selected = relative_isolation[ak.fill_none(baseline_mask, False)]
        values = ak.to_numpy(ak.drop_none(selected)).astype(np.float64, copy=False)

        self.baseline_events += len(selected)
        if values.size == 0:
            return

        finite_mask = np.isfinite(values)
        finite = values[finite_mask]
        self.finite_values += int(finite.size)
        self.nonfinite_values += int(values.size - finite.size)
        if finite.size == 0:
            return

        self.negative_values += int(np.count_nonzero(finite < 0.0))
        self.minimum = min(self.minimum, float(np.min(finite)))
        self.maximum = max(self.maximum, float(np.max(finite)))

        remaining = self.sample_limit - self.sampled_count
        if remaining > 0:
            sample = finite[:remaining].copy()
            self.sampled_values.append(sample)
            self.sampled_count += int(sample.size)

    def sample(self) -> np.ndarray:
        if not self.sampled_values:
            return np.empty(0, dtype=np.float64)
        return np.concatenate(self.sampled_values)


def print_track_isolation_summary(
    diagnostics: TrackIsolationDiagnostics, threshold: float
) -> None:
    sample = diagnostics.sample()
    if sample.size == 0:
        print("\nTRACK-ISOLATION DIAGNOSTIC")
        print("No finite values were available.")
        return

    percentiles = np.percentile(sample, [1, 25, 50, 75, 90, 95, 99])
    sample_efficiency = float(np.mean(sample < threshold))

    print("\nTRACK-ISOLATION DIAGNOSTIC")
    print("Definition              : lep_ptcone30 / lep_pt")
    print(f"Events after tight ID   : {diagnostics.baseline_events:,}")
    print(f"Finite values           : {diagnostics.finite_values:,}")
    print(f"Non-finite values       : {diagnostics.nonfinite_values:,}")
    print(f"Negative finite values  : {diagnostics.negative_values:,}")
    print(f"Finite minimum          : {diagnostics.minimum:.6f}")
    print(f"Finite maximum          : {diagnostics.maximum:.6f}")
    print(f"Diagnostic sample size  : {sample.size:,}")
    print(f"Sample fraction below {threshold:g}: {sample_efficiency:.2%}")

    labels = ("1st", "25th", "median", "75th", "90th", "95th", "99th")
    print("\nRelative track-isolation percentiles")
    print("Percentile       ptcone30 / pT")
    print("-----------------------------")
    for label, value in zip(labels, percentiles, strict=True):
        print(f"{label:<12}  {value:>13.6f}")


@dataclass
class ElectronPtDiagnostics:
    """Streaming diagnostic for the selected-electron transverse momentum."""

    sample_limit: int = 200_000
    selected_events: int = 0
    one_electron_events: int = 0
    multiple_electron_events: int = 0
    maximum_electrons_in_event: int = 0
    raw_minimum: float = float("inf")
    raw_maximum: float = float("-inf")
    sampled_values: list[np.ndarray] = field(default_factory=list)
    sampled_count: int = 0

    def update(self, electron: SelectedElectron) -> None:
        counts = ak.to_numpy(electron.count)
        self.one_electron_events += int(np.count_nonzero(counts == 1))
        self.multiple_electron_events += int(np.count_nonzero(counts > 1))
        if counts.size:
            self.maximum_electrons_in_event = max(
                self.maximum_electrons_in_event, int(np.max(counts))
            )

        values = ak.to_numpy(ak.drop_none(electron.pt_raw)).astype(
            np.float64, copy=False
        )
        if values.size == 0:
            return

        self.selected_events += int(values.size)
        self.raw_minimum = min(self.raw_minimum, float(np.min(values)))
        self.raw_maximum = max(self.raw_maximum, float(np.max(values)))
        remaining = self.sample_limit - self.sampled_count
        if remaining > 0:
            sample = values[:remaining].copy()
            self.sampled_values.append(sample)
            self.sampled_count += int(sample.size)

    def sample(self) -> np.ndarray:
        if not self.sampled_values:
            return np.empty(0, dtype=np.float64)
        return np.concatenate(self.sampled_values)


def infer_pt_unit(sample: np.ndarray) -> tuple[str, float]:
    if sample.size == 0:
        raise ValueError("Cannot infer lep_pt units from an empty sample")
    median = float(np.median(sample))
    if median >= 1_000.0:
        return "MeV", 1.0e-3
    if median >= 1.0:
        return "GeV", 1.0
    raise ValueError(
        "lep_pt values are too small for reliable unit inference. "
        f"Sample median: {median:g}"
    )


def print_electron_pt_summary(diagnostics: ElectronPtDiagnostics) -> None:
    sample = diagnostics.sample()
    unit, gev_scale = infer_pt_unit(sample)
    percentiles = np.percentile(sample, [1, 25, 50, 75, 99])

    print("\nSELECTED-ELECTRON DIAGNOSTIC")
    print(f"Events with a selected electron : {diagnostics.selected_events:,}")
    print(f"Events with exactly one electron: {diagnostics.one_electron_events:,}")
    print(f"Events with multiple electrons  : {diagnostics.multiple_electron_events:,}")
    print(
        "Maximum electron multiplicity : "
        f"{diagnostics.maximum_electrons_in_event}"
    )
    print("\nlep_pt scale")
    print(f"Diagnostic sample size : {sample.size:,}")
    print(f"Raw minimum            : {diagnostics.raw_minimum:,.3f}")
    print(f"Raw maximum            : {diagnostics.raw_maximum:,.3f}")
    print(f"Inferred stored unit   : {unit}")
    print(f"Conversion to GeV      : raw lep_pt × {gev_scale:g}")

    labels = ("1st", "25th", "median", "75th", "99th")
    print("\nSelected-electron pT percentiles")
    print("Percentile          raw value       value [GeV]")
    print("------------------------------------------------")
    for label, raw_value in zip(labels, percentiles, strict=True):
        print(
            f"{label:<12}  {raw_value:>14,.3f}  "
            f"{raw_value * gev_scale:>16.3f}"
        )


def update_lepton_type_counts(
    arrays: ak.Array, branch_name: str, counts: dict[int, int]
) -> None:
    flattened = ak.flatten(arrays[branch_name], axis=None)
    if len(flattened) == 0:
        return
    values = np.abs(ak.to_numpy(flattened)).astype(np.int64, copy=False)
    unique_values, unique_counts = np.unique(values, return_counts=True)
    for value, count in zip(unique_values, unique_counts, strict=True):
        counts[int(value)] += int(count)


@dataclass(frozen=True)
class AnalysisSummary:
    cutflow: CutFlow
    lepton_type_counts: dict[int, int]
    electron_pt_diagnostics: ElectronPtDiagnostics
    track_isolation_diagnostics: TrackIsolationDiagnostics


ChunkObserver = Callable[
    [ak.Array, SelectedElectron, Mapping[str, ak.Array]], None
]


def process_files(
    root_files: Sequence[Path],
    tree_name: str,
    branches: BranchMap,
    step_size: str,
    electron_pt_min_gev: float,
    track_isolation_max: float,
    *,
    on_chunk: ChunkObserver | None = None,
) -> AnalysisSummary:
    """Process ROOT files once and accumulate shared analysis diagnostics."""

    pt_selection = electron_pt_selection_name(electron_pt_min_gev)
    eta_coverage_selection = eta_coverage_selection_name()
    eta_transition_selection = eta_transition_veto_selection_name()
    tight_selection = tight_id_selection_name()
    isolation_selection = track_isolation_selection_name(track_isolation_max)

    cutflow = CutFlow(
        selection_order=(
            "All events",
            "At least one reconstructed lepton",
            "At least one electron candidate",
            pt_selection,
            eta_coverage_selection,
            eta_transition_selection,
            tight_selection,
            isolation_selection,
        )
    )
    lepton_type_counts: dict[int, int] = defaultdict(int)
    electron_pt_diagnostics = ElectronPtDiagnostics()
    track_isolation_diagnostics = TrackIsolationDiagnostics()

    for file_index, file_path in enumerate(root_files, start=1):
        print(f"\nProcessing file {file_index}/{len(root_files)}: {file_path.name}")
        with open_root_file(file_path) as root_file:
            tree = root_file[tree_name]
            missing = sorted(set(branches.required()) - set(tree.keys()))
            if missing:
                raise KeyError(
                    f"{file_path.name} is missing branches: " + ", ".join(missing)
                )

            for chunk_index, arrays in enumerate(
                tree.iterate(
                    expressions=list(branches.required()),
                    step_size=step_size,
                    library="ak",
                ),
                start=1,
            ):
                electron = select_event_electron(arrays, branches)
                masks = build_initial_masks(
                    arrays,
                    branches,
                    electron,
                    electron_pt_min_gev,
                    track_isolation_max,
                )
                track_isolation_diagnostics.update(
                    electron.relative_track_isolation, masks[tight_selection]
                )
                if on_chunk is not None:
                    on_chunk(arrays, electron, masks)

                cutflow.add_count("All events", len(arrays))
                for selection, mask in masks.items():
                    cutflow.add_count(selection, count_true(mask))
                update_lepton_type_counts(
                    arrays, branches.lepton_type, lepton_type_counts
                )
                electron_pt_diagnostics.update(electron)
                print(
                    f"  chunk {chunk_index:>3}: {len(arrays):>9,d} events",
                    end="\r",
                    flush=True,
                )

        print(" " * 70, end="\r")
        print(f"  completed: {file_path.name}")

    return AnalysisSummary(
        cutflow=cutflow,
        lepton_type_counts=dict(sorted(lepton_type_counts.items())),
        electron_pt_diagnostics=electron_pt_diagnostics,
        track_isolation_diagnostics=track_isolation_diagnostics,
    )


def print_lepton_type_summary(counts: Mapping[int, int]) -> None:
    print("\nLEPTON-TYPE DIAGNOSTIC")
    print("|lep_type|  Candidates  Interpretation")
    print("--------------------------------------")
    for lepton_type, count in counts.items():
        interpretation = {11: "electron", 13: "muon", 15: "tau"}.get(
            lepton_type, "other / inspect"
        )
        print(f"{lepton_type:>10}  {count:>10,d}  {interpretation}")
