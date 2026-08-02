#!/usr/bin/env python3
"""
Very simple ATLAS Open Data example:
compare the dielectron invariant-mass distribution before and after
a basic event selection.

This is NOT yet a matrix-method background estimate.
It is only a visual prototype showing how a cleaner Z -> e+e- peak
can emerge after tight identification, isolation and charge cuts.

Install:
    pip install uproot awkward vector numpy matplotlib

Run:
    python z_pre_post_uproot.py data.root
    python z_pre_post_uproot.py "data/*.root"
"""

from __future__ import annotations

import argparse
import glob

import awkward as ak
import matplotlib.pyplot as plt
import numpy as np
import uproot
import vector


REQUIRED_LEPTON_BRANCHES = (
    "lep_pt",
    "lep_eta",
    "lep_phi",
    "lep_charge",
    "lep_type",
    "lep_isTightID",
    "lep_ptcone30",
    "lep_etcone20",
)
ENERGY_BRANCHES = ("lep_e", "lep_E")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "files",
        nargs="+",
        help="ROOT file, URL, or glob such as data/*.root",
    )
    parser.add_argument(
        "--tree",
        default=None,
        help="TTree name (default: auto-detect a compatible tree)",
    )
    parser.add_argument(
        "--step-size",
        default="100 MB",
        help="Chunk size used by uproot (default: 100 MB)",
    )
    return parser.parse_args()


def expand_inputs(items: list[str]) -> list[str]:
    """Expand local glob patterns, while leaving URLs untouched."""
    output: list[str] = []

    for item in items:
        matches = glob.glob(item)

        if matches:
            output.extend(sorted(matches))
        else:
            output.append(item)

    return output


def open_root_file(filename: str):
    """Open local files without fsspec; retain uproot's URL handling remotely."""
    options = {}

    # uproot 5.7/fsspec can stall on local reads under Python 3.14.  The native
    # file source is also the most direct backend for ordinary filesystem paths.
    if "://" not in filename:
        options["handler"] = uproot.MultithreadedFileSource

    return uproot.open(filename, **options)


def select_tree(root_file, requested: str | None, filename: str):
    """Return the requested tree, or uniquely identify a compatible one."""
    classnames = root_file.classnames(cycle=False)
    tree_names = [
        name
        for name, classname in classnames.items()
        if classname in {"TTree", "ROOT::RNTuple"}
    ]

    if requested is not None:
        if requested not in root_file:
            available = ", ".join(tree_names) or "none"
            raise KeyError(
                f"Tree '{requested}' not found in {filename}.\n"
                f"Available trees: {available}"
            )
        return requested, root_file[requested]

    compatible: list[str] = []
    for name in tree_names:
        branch_names = set(root_file[name].keys())
        has_energy = any(branch in branch_names for branch in ENERGY_BRANCHES)
        if has_energy and all(
            branch in branch_names for branch in REQUIRED_LEPTON_BRANCHES
        ):
            compatible.append(name)

    if len(compatible) == 1:
        name = compatible[0]
        return name, root_file[name]

    if not compatible and len(tree_names) == 1:
        # Let the branch validation below report exactly what is missing.
        name = tree_names[0]
        return name, root_file[name]

    if not tree_names:
        available = ", ".join(classnames) or "none"
        raise KeyError(
            f"No TTree or RNTuple found in {filename}.\n"
            f"Available objects: {available}"
        )

    choices = compatible or tree_names
    raise ValueError(
        f"Could not choose a unique tree in {filename}: {', '.join(choices)}. "
        "Pass its name with --tree."
    )


def energy_branch(tree: uproot.behaviors.TTree.TTree) -> str:
    """Support both recent 'lep_e' and older 'lep_E' naming."""
    names = set(tree.keys())

    for name in ENERGY_BRANCHES:
        if name in names:
            return name

    raise KeyError("Neither 'lep_e' nor 'lep_E' exists in this tree.")


def infer_gev_scale(pt: ak.Array) -> float:
    """
    ATLAS educational ntuples are often stored in MeV.
    If typical pT values are much larger than hundreds, convert MeV -> GeV.
    """
    flat = ak.to_numpy(ak.flatten(pt, axis=None))

    if len(flat) == 0:
        return 1.0

    return 0.001 if np.nanmedian(flat) > 500 else 1.0


def calculate_mass(pair: ak.Array, scale: float) -> ak.Array:
    """Invariant mass of the two leading electron candidates."""
    p4 = vector.zip(
        {
            "pt": pair.pt * scale,
            "eta": pair.eta,
            "phi": pair.phi,
            "e": pair.energy * scale,
        }
    )

    return (p4[:, 0] + p4[:, 1]).mass


def process_file(
    filename: str,
    tree_name: str | None,
    step_size: str,
) -> tuple[list[np.ndarray], list[np.ndarray]]:
    pre_chunks: list[np.ndarray] = []
    post_chunks: list[np.ndarray] = []

    with open_root_file(filename) as root_file:
        selected_tree_name, tree = select_tree(root_file, tree_name, filename)
        print(f"  Using tree: {selected_tree_name}")
        e_branch = energy_branch(tree)

        required = [*REQUIRED_LEPTON_BRANCHES, e_branch]

        branch_names = set(tree.keys())
        missing = [name for name in required if name not in branch_names]
        if missing:
            raise KeyError(
                f"Missing branches in tree '{selected_tree_name}' "
                f"of {filename}: {missing}"
            )

        for arrays in tree.iterate(
            required,
            step_size=step_size,
            library="ak",
        ):
            leptons = ak.zip(
                {
                    "pt": arrays["lep_pt"],
                    "eta": arrays["lep_eta"],
                    "phi": arrays["lep_phi"],
                    "energy": arrays[e_branch],
                    "charge": arrays["lep_charge"],
                    # "type" is an Awkward Array property, so it cannot be
                    # accessed reliably as a record field with attribute syntax.
                    "pdg_id": arrays["lep_type"],
                    "tight": arrays["lep_isTightID"],
                    "ptcone30": arrays["lep_ptcone30"],
                    "etcone20": arrays["lep_etcone20"],
                }
            )

            # Keep electron candidates only. ATLAS uses |PDG ID| = 11 for electrons.
            electrons = leptons[abs(leptons.pdg_id) == 11]

            # Sort candidates by transverse momentum.
            order = ak.argsort(electrons.pt, axis=1, ascending=False)
            electrons = electrons[order]

            # Require at least two candidates, then keep the two leading ones.
            has_two = ak.num(electrons.pt, axis=1) >= 2
            pair = electrons[has_two][:, :2]

            if len(pair) == 0:
                continue

            scale = infer_gev_scale(pair.pt)
            mass = calculate_mass(pair, scale)

            pt = pair.pt * scale
            abs_eta = abs(pair.eta)

            # BEFORE:
            # very loose acceptance cuts only.
            pre_mask = (
                (pt[:, 0] > 10)
                & (pt[:, 1] > 10)
                & (abs_eta[:, 0] < 2.47)
                & (abs_eta[:, 1] < 2.47)
            )

            # AFTER:
            # tighter and more physically motivated cuts.
            opposite_charge = pair.charge[:, 0] * pair.charge[:, 1] < 0
            both_tight = ak.all(pair.tight, axis=1)

            track_isolation = pair.ptcone30 / pair.pt
            calo_isolation = pair.etcone20 / pair.pt
            both_isolated = ak.all(
                (track_isolation < 0.15) & (calo_isolation < 0.15),
                axis=1,
            )

            outside_crack = ak.all(
                (abs_eta < 1.37) | (abs_eta > 1.52),
                axis=1,
            )

            post_mask = (
                pre_mask
                & (pt[:, 0] > 25)
                & (pt[:, 1] > 20)
                & opposite_charge
                & both_tight
                & both_isolated
                & outside_crack
            )

            pre_chunks.append(ak.to_numpy(mass[pre_mask]))
            post_chunks.append(ak.to_numpy(mass[post_mask]))

    return pre_chunks, post_chunks


def save_histogram(values: np.ndarray, title: str, output: str) -> None:
    bins = np.linspace(40, 140, 51)

    fig, ax = plt.subplots(figsize=(7, 5))
    ax.hist(values, bins=bins, histtype="stepfilled", alpha=0.8)
    ax.axvline(
        91.2,
        linestyle="--",
        linewidth=1.5,
        label=r"$m_Z \approx 91.2$ GeV",
    )

    ax.set_xlim(40, 140)
    ax.set_xlabel(r"Dielectron invariant mass $m_{ee}$ [GeV]")
    ax.set_ylabel("Events / 2 GeV")
    ax.set_title(title)
    ax.legend()
    ax.grid(alpha=0.2)

    fig.tight_layout()
    fig.savefig(output, dpi=220)
    plt.close(fig)


def main() -> None:
    args = parse_args()
    files = expand_inputs(args.files)

    all_pre: list[np.ndarray] = []
    all_post: list[np.ndarray] = []

    for filename in files:
        print(f"Reading {filename}")
        pre, post = process_file(filename, args.tree, args.step_size)
        all_pre.extend(pre)
        all_post.extend(post)

    pre_mass = np.concatenate(all_pre) if all_pre else np.array([])
    post_mass = np.concatenate(all_post) if all_post else np.array([])

    if pre_mass.size == 0:
        raise RuntimeError("No dielectron candidates survived the loose selection.")

    print(f"Loose candidates: {len(pre_mass)}")
    print(f"Selected candidates: {len(post_mass)}")

    save_histogram(
        pre_mass,
        "Before analysis: all electron-like pairs",
        "pre_analysis.png",
    )

    save_histogram(
        post_mass,
        "After analysis: the Z peak emerges",
        "post_analysis.png",
    )

    print("Saved:")
    print("  pre_analysis.png")
    print("  post_analysis.png")


if __name__ == "__main__":
    main()
