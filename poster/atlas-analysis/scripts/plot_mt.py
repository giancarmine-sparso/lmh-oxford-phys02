#!/usr/bin/env python3
"""Generate the final transverse-mass plots."""

from __future__ import annotations

import argparse
from pathlib import Path

from atlas_analysis.selection import DEFAULT_DATA_FILE
from atlas_analysis.mt import DEFAULT_OUTPUT_DIR, MtConfig, run_mt


def parse_arguments() -> MtConfig:
    parser = argparse.ArgumentParser(
        description="Generate the ATLAS Open Data transverse-mass comparisons."
    )
    parser.add_argument(
        "input_path",
        nargs="?",
        type=Path,
        default=DEFAULT_DATA_FILE,
        help="ROOT file or directory; default: data/1lep/Data/data_A.1lep.root",
    )
    parser.add_argument(
        "--tree",
        dest="tree_name",
        default="mini",
        help="TTree name; default: mini",
    )
    parser.add_argument(
        "--step-size",
        default="200 MB",
        help="Chunk size passed to uproot; default: '200 MB'",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory for the generated PNG/PDF plot pairs; default: plots/final",
    )
    args = parser.parse_args()
    return MtConfig(
        input_path=args.input_path,
        tree_name=args.tree_name,
        step_size=args.step_size,
        output_dir=args.output_dir,
    )


def main() -> None:
    run_mt(parse_arguments())


if __name__ == "__main__":
    main()
