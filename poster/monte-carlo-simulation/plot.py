from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


DATA_PATH = Path("output/events.csv")
OUTPUT_PATH = Path("output/before_after.png")


def purity(data: pd.DataFrame) -> float:
    if len(data) == 0:
        return 0.0

    return float((data["process"] == "signal").mean())


def main() -> None:
    if not DATA_PATH.exists():
        raise FileNotFoundError(
            f"{DATA_PATH} non esiste. Esegui prima `cargo run --release`."
        )

    events = pd.read_csv(DATA_PATH)

    # Selezione iniziale: richiediamo soltanto un candidato
    # con momento trasverso minimo.
    loose_selection = events[events["electron_pt"] > 20.0]

    # Selezione signal-like.
    tight_selection = events[
        (events["electron_pt"] > 25.0)
        & (events["met"] > 30.0)
        & (events["isolation"] < 0.10)
        & events["tight_id"]
    ]

    bins = np.linspace(0.0, 160.0, 41)

    plt.rcParams.update(
        {
            "font.size": 14,
            "axes.titlesize": 19,
            "axes.labelsize": 17,
            "legend.fontsize": 13,
        }
    )

    figure, axes = plt.subplots(
        nrows=1,
        ncols=2,
        figsize=(15, 6),
        sharex=True,
        sharey=True,
    )

    selections = [
        (
            loose_selection,
            "Before background rejection",
            r"Loose selection: $p_T^e > 20$ GeV",
        ),
        (
            tight_selection,
            "After background rejection",
            (
                r"$p_T^e > 25$ GeV, "
                r"$E_T^{\mathrm{miss}} > 30$ GeV"
                "\n"
                r"isolation $< 0.10$ and tight ID"
            ),
        ),
    ]

    for axis, (selection, title, subtitle) in zip(axes, selections):
        background = selection.loc[
            selection["process"] == "qcd",
            "transverse_mass",
        ]

        signal = selection.loc[
            selection["process"] == "signal",
            "transverse_mass",
        ]

        axis.hist(
            [background, signal],
            bins=bins,
            stacked=True,
            label=["QCD-like background", r"$W\rightarrow e\nu$ signal"],
        )

        axis.set_title(title)
        axis.set_xlabel(r"Transverse mass $m_T$ [GeV]")
        axis.set_xlim(0.0, 160.0)
        axis.grid(alpha=0.25)

        annotation = (
            f"{subtitle}\n"
            f"Selected events: {len(selection):,}\n"
            f"Signal fraction: {100.0 * purity(selection):.1f}%"
        )

        axis.text(
            0.97,
            0.96,
            annotation,
            transform=axis.transAxes,
            horizontalalignment="right",
            verticalalignment="top",
            fontsize=12,
        )

    axes[0].set_ylabel("Simulated events / 4 GeV")
    axes[1].legend(loc="center right")

    figure.suptitle(
        r"Toy Monte Carlo: extracting $W\rightarrow e\nu$ from background",
        fontsize=22,
    )

    figure.tight_layout()
    figure.savefig(OUTPUT_PATH, dpi=220, bbox_inches="tight")

    print(f"Loose events: {len(loose_selection):,}")
    print(f"Tight events: {len(tight_selection):,}")
    print(f"Loose signal fraction: {100 * purity(loose_selection):.2f}%")
    print(f"Tight signal fraction: {100 * purity(tight_selection):.2f}%")
    print(f"Plot written to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
