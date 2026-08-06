#!/usr/bin/env python3
"""Run the ATLAS Open Data cut-flow and ABCD estimate."""

from __future__ import annotations

import argparse
from pathlib import Path

from atlas_analysis.abcd import (
    ABCDAnalysisConfig,
    DEFAULT_ABCD_ISO_CONTROL_MIN,
    DEFAULT_ABCD_ISO_SIGNAL_MAX,
    DEFAULT_ABCD_MET_CONTROL_MAX_GEV,
    DEFAULT_ABCD_MET_SIGNAL_MIN_GEV,
    DEFAULT_ABCD_PLOT_PATH,
    run_abcd_analysis,
)
from atlas_analysis.selection import (
    DEFAULT_DATA_DIR,
    DEFAULT_ELECTRON_PT_MIN_GEV,
    DEFAULT_TRACK_ISOLATION_MAX,
)


def parse_arguments() -> ABCDAnalysisConfig:
    parser = argparse.ArgumentParser(
        description=(
            "Run the phase-1 cut-flow and a data-driven ABCD estimate "
            "using relative track isolation and missing transverse momentum."
        )
    )
    parser.add_argument(
        "input_path",
        nargs="?",
        type=Path,
        default=DEFAULT_DATA_DIR,
        help="ROOT file or directory. Default: <project>/data/1lep/Data",
    )
    parser.add_argument(
        "--tree",
        dest="tree_name",
        default=None,
        help="TTree name; default: auto-detect 'mini'",
    )
    parser.add_argument(
        "--max-files",
        type=int,
        default=1,
        help="Maximum number of files to process; default: 1",
    )
    parser.add_argument(
        "--all-files",
        action="store_true",
        help="Process every ROOT file found under the input path",
    )
    parser.add_argument(
        "--step-size",
        default="100 MB",
        help="Chunk size passed to uproot; default: '100 MB'",
    )
    parser.add_argument(
        "--electron-pt-min",
        type=float,
        default=DEFAULT_ELECTRON_PT_MIN_GEV,
        help=f"Minimum selected-electron pT in GeV; default: {DEFAULT_ELECTRON_PT_MIN_GEV:g}",
    )
    parser.add_argument(
        "--track-iso-max",
        type=float,
        default=DEFAULT_TRACK_ISOLATION_MAX,
        help=(
            "Maximum relative track isolation lep_ptcone30/lep_pt; "
            f"default: {DEFAULT_TRACK_ISOLATION_MAX:g}"
        ),
    )
    parser.add_argument(
        "--met-branch",
        default="met_et",
        help="Missing-transverse-momentum magnitude branch; default: met_et",
    )
    parser.add_argument(
        "--abcd-iso-signal-max",
        type=float,
        default=DEFAULT_ABCD_ISO_SIGNAL_MAX,
        help=f"Upper isolation boundary for A/C; default: {DEFAULT_ABCD_ISO_SIGNAL_MAX:g}",
    )
    parser.add_argument(
        "--abcd-iso-control-min",
        type=float,
        default=DEFAULT_ABCD_ISO_CONTROL_MIN,
        help=f"Lower non-isolated boundary for B/D; default: {DEFAULT_ABCD_ISO_CONTROL_MIN:g}",
    )
    parser.add_argument(
        "--abcd-met-control-max",
        type=float,
        default=DEFAULT_ABCD_MET_CONTROL_MAX_GEV,
        help=(
            "Upper low-MET boundary for C/D in GeV; "
            f"default: {DEFAULT_ABCD_MET_CONTROL_MAX_GEV:g}"
        ),
    )
    parser.add_argument(
        "--abcd-met-signal-min",
        type=float,
        default=DEFAULT_ABCD_MET_SIGNAL_MIN_GEV,
        help=(
            "Lower high-MET boundary for A/B in GeV; "
            f"default: {DEFAULT_ABCD_MET_SIGNAL_MIN_GEV:g}"
        ),
    )
    parser.add_argument(
        "--abcd-plot",
        type=Path,
        default=DEFAULT_ABCD_PLOT_PATH,
        help="Primary ABCD plot path; matching PNG and PDF variants are also written",
    )

    args = parser.parse_args()
    if args.max_files is not None and args.max_files <= 0:
        parser.error("--max-files must be positive")
    if args.electron_pt_min <= 0:
        parser.error("--electron-pt-min must be positive")
    if args.track_iso_max <= 0:
        parser.error("--track-iso-max must be positive")
    if args.abcd_iso_signal_max < 0:
        parser.error("--abcd-iso-signal-max cannot be negative")
    if args.abcd_iso_control_min < args.abcd_iso_signal_max:
        parser.error("--abcd-iso-control-min must be >= --abcd-iso-signal-max")
    if args.abcd_met_control_max < 0:
        parser.error("--abcd-met-control-max cannot be negative")
    if args.abcd_met_signal_min < args.abcd_met_control_max:
        parser.error("--abcd-met-signal-min must be >= --abcd-met-control-max")

    return ABCDAnalysisConfig(
        input_path=args.input_path,
        tree_name=args.tree_name,
        max_files=None if args.all_files else args.max_files,
        step_size=args.step_size,
        electron_pt_min_gev=args.electron_pt_min,
        track_isolation_max=args.track_iso_max,
        met_branch=args.met_branch,
        abcd_iso_signal_max=args.abcd_iso_signal_max,
        abcd_iso_control_min=args.abcd_iso_control_min,
        abcd_met_control_max_gev=args.abcd_met_control_max,
        abcd_met_signal_min_gev=args.abcd_met_signal_min,
        abcd_plot_path=args.abcd_plot,
    )


def main() -> None:
    run_abcd_analysis(parse_arguments())


if __name__ == "__main__":
    main()
