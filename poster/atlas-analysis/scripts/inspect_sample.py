#!/usr/bin/env python3
"""Inspect a small slice of an ATLAS Open Data ROOT sample."""

from __future__ import annotations

import argparse
from pathlib import Path

import awkward as ak
import numpy as np

from atlas_analysis.selection import DEFAULT_DATA_FILE, choose_tree, open_root_file


BRANCHES = (
    "trigE",
    "trigM",
    "lep_n",
    "lep_pt",
    "lep_eta",
    "lep_phi",
    "lep_type",
    "lep_isTightID",
    "lep_ptcone30",
    "lep_etcone20",
    "met_et",
    "met_phi",
)


def flattened(array: ak.Array) -> np.ndarray:
    return ak.to_numpy(ak.flatten(array, axis=None))


def print_values_and_counts(name: str, array: ak.Array) -> None:
    values = flattened(array)
    unique, counts = np.unique(values, return_counts=True)
    print(f"\n{name}:")
    for value, count in zip(unique, counts, strict=True):
        print(f"  {value!r}: {count:,}")


def inspect_sample(input_path: Path, tree_name: str | None, events: int) -> None:
    input_path = input_path.expanduser().resolve()
    if not input_path.is_file():
        raise FileNotFoundError(f"ROOT file not found: {input_path}")

    with open_root_file(input_path) as root_file:
        selected_tree = choose_tree(root_file, tree_name)
        tree = root_file[selected_tree]
        missing = sorted(set(BRANCHES) - set(tree.keys()))
        if missing:
            raise KeyError("Required branches are missing: " + ", ".join(missing))
        arrays = tree.arrays(
            list(BRANCHES),
            entry_start=0,
            entry_stop=events,
            library="ak",
        )

    print(f"Events inspected: {len(arrays):,}")
    for branch in ("lep_n", "lep_type", "lep_isTightID", "trigE", "trigM"):
        print_values_and_counts(branch, arrays[branch])

    lep_pt = flattened(arrays["lep_pt"])
    met_et = flattened(arrays["met_et"])
    if lep_pt.size == 0 or met_et.size == 0:
        raise RuntimeError("The selected sample contains no pT or MET values.")

    print("\nlep_pt — raw values:")
    print(f"  minimum: {lep_pt.min():.2f}")
    print(f"  median : {np.median(lep_pt):.2f}")
    print(f"  95%    : {np.quantile(lep_pt, 0.95):.2f}")
    print(f"  maximum: {lep_pt.max():.2f}")

    print("\nlep_pt / 1000 — GeV hypothesis:")
    print(f"  minimum: {lep_pt.min() / 1000:.2f} GeV")
    print(f"  median : {np.median(lep_pt) / 1000:.2f} GeV")
    print(f"  95%    : {np.quantile(lep_pt, 0.95) / 1000:.2f} GeV")
    print(f"  maximum: {lep_pt.max() / 1000:.2f} GeV")

    print("\nmet_et / 1000:")
    print(f"  minimum: {met_et.min() / 1000:.2f} GeV")
    print(f"  median : {np.median(met_et) / 1000:.2f} GeV")
    print(f"  95%    : {np.quantile(met_et, 0.95) / 1000:.2f} GeV")
    print(f"  maximum: {met_et.max() / 1000:.2f} GeV")

    ptcone30 = flattened(arrays["lep_ptcone30"])
    valid_pt = lep_pt > 0
    relative_isolation = ptcone30[valid_pt] / lep_pt[valid_pt]
    print("\nRelative isolation lep_ptcone30 / lep_pt:")
    print(f"  median: {np.median(relative_isolation):.4f}")
    print(f"  90%   : {np.quantile(relative_isolation, 0.90):.4f}")
    print(f"  95%   : {np.quantile(relative_isolation, 0.95):.4f}")


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "input_path",
        nargs="?",
        type=Path,
        default=DEFAULT_DATA_FILE,
        help="ROOT file; default: data/1lep/Data/data_A.1lep.root",
    )
    parser.add_argument("--tree", default="mini", help="TTree name; default: mini")
    parser.add_argument(
        "--events",
        type=int,
        default=100_000,
        help="Maximum events to inspect; default: 100000",
    )
    args = parser.parse_args()
    if args.events <= 0:
        parser.error("--events must be positive")
    return args


def main() -> None:
    args = parse_arguments()
    inspect_sample(args.input_path, args.tree, args.events)


if __name__ == "__main__":
    main()
