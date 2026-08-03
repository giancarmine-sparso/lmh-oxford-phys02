"""
Analisi preliminare H -> gamma gamma su ATLAS Open Data (rilascio 2020, tree 'mini').

Uso:
    python hyy_preliminary.py data/data_*.GamGam.root

Produce due figure:
    gg_pre_analysis.png   spettro grezzo: il picco NON si vede
    gg_post_analysis.png  dati - fondo stimato dalle sidebands: il picco emerge
"""

import sys
import numpy as np
import awkward as ak
import uproot
import matplotlib.pyplot as plt
from scipy.optimize import curve_fit

# --- selezione standard ATLAS per il canale difotone -----------------------
PT_MIN = 25_000.0  # MeV
ETA_MAX = 2.37
CRACK = (1.37, 1.52)  # regione di transizione barrel/endcap, esclusa
ISO_MAX = 0.065  # ptcone30/pt e etcone20/pt

# --- binning e finestra di segnale ----------------------------------------
M_LO, M_HI, N_BINS = 105.0, 160.0, 30
SIG_LO, SIG_HI = 120.0, 130.0  # esclusa dal fit: e' la finestra di segnale

BRANCHES = [
    "trigP",
    "photon_pt",
    "photon_eta",
    "photon_phi",
    "photon_E",
    "photon_isTightID",
    "photon_ptcone30",
    "photon_etcone20",
]


def invariant_mass(pt, eta, phi, e):
    """Massa invariante (GeV) dei primi due fotoni di ogni evento."""
    px = pt * np.cos(phi)
    py = pt * np.sin(phi)
    pz = pt * np.sinh(eta)
    px, py, pz, e = (ak.sum(v, axis=1) for v in (px, py, pz, e))
    m2 = e**2 - px**2 - py**2 - pz**2
    return np.sqrt(np.maximum(ak.to_numpy(m2), 0.0)) / 1000.0


def select(ev):
    """Applica la selezione e restituisce m_yy in GeV."""
    ev = ev[ev.trigP]

    abs_eta = abs(ev.photon_eta)
    good = (
        ev.photon_isTightID
        & (ev.photon_pt > PT_MIN)
        & (abs_eta < ETA_MAX)
        & ((abs_eta < CRACK[0]) | (abs_eta > CRACK[1]))
        & (ev.photon_ptcone30 / ev.photon_pt < ISO_MAX)
        & (ev.photon_etcone20 / ev.photon_pt < ISO_MAX)
    )
    two = ak.sum(good, axis=1) == 2
    ev, good = ev[two], good[two]

    if len(ev) == 0:
        return np.array([])

    pt = ev.photon_pt[good]
    # ordina per pt decrescente: serve per i tagli su pt/m
    order = ak.argsort(pt, axis=1, ascending=False)
    pt = pt[order]
    eta = ev.photon_eta[good][order]
    phi = ev.photon_phi[good][order]
    ene = ev.photon_E[good][order]

    m = invariant_mass(pt, eta, phi, ene)
    lead = ak.to_numpy(pt[:, 0]) / 1000.0
    sub = ak.to_numpy(pt[:, 1]) / 1000.0

    with np.errstate(divide="ignore", invalid="ignore"):
        keep = (m > M_LO) & (m < M_HI) & (lead / m > 0.35) & (sub / m > 0.25)
    return m[keep]


def poly3(x, a, b, c, d):
    return a + b * x + c * x**2 + d * x**3


def main(paths):
    masses = []
    for path in paths:
        print(f"leggo {path}")
        for ev in uproot.iterate(f"{path}:mini", BRANCHES, step_size="50 MB"):
            masses.append(select(ev))
    m = np.concatenate([x for x in masses if len(x)])
    print(f"{len(m)} eventi dopo la selezione")

    counts, edges = np.histogram(m, bins=N_BINS, range=(M_LO, M_HI))
    centres = 0.5 * (edges[:-1] + edges[1:])
    errors = np.sqrt(counts)

    # --- fit del fondo sulle sole sidebands ------------------------------
    side = (centres < SIG_LO) | (centres > SIG_HI)
    x = (centres - M_LO) / (M_HI - M_LO)  # riscalato in [0,1]
    popt, _ = curve_fit(
        poly3,
        x[side],
        counts[side],
        sigma=np.maximum(errors[side], 1.0),
        absolute_sigma=True,
        p0=[counts[0], 0.0, 0.0, 0.0],
    )
    bkg = poly3(x, *popt)

    n_sig = counts[~side].sum() - bkg[~side].sum()
    n_bkg = bkg[~side].sum()
    print(
        f"finestra {SIG_LO}-{SIG_HI} GeV: "
        f"S = {n_sig:.0f}, B = {n_bkg:.0f}, S/B = {n_sig / n_bkg:.3f}, "
        f"S/sqrt(B) = {n_sig / np.sqrt(n_bkg):.1f}"
    )

    # --- figura 1: spettro grezzo ----------------------------------------
    fig, ax = plt.subplots(figsize=(8, 6), constrained_layout=True)
    ax.errorbar(
        centres, counts, yerr=errors, fmt="o", color="black", markersize=4, label="Dati"
    )
    ax.plot(
        centres, bkg, "--", color="#0072B2", lw=2, label="Fondo (fit sulle sidebands)"
    )
    ax.axvspan(
        SIG_LO,
        SIG_HI,
        color="grey",
        alpha=0.12,
        label="Finestra di segnale (esclusa dal fit)",
    )
    ax.set_xlabel(r"$m_{\gamma\gamma}$ [GeV]")
    ax.set_ylabel(f"Eventi / {(M_HI - M_LO) / N_BINS:.1f} GeV")
    ax.set_title("Prima: lo spettro grezzo")
    ax.set_xlim(M_LO, M_HI)
    ax.legend()
    fig.savefig("gg_pre_analysis.png", dpi=200, bbox_inches="tight")
    plt.close(fig)

    # --- figura 2: residuo ------------------------------------------------
    fig, ax = plt.subplots(figsize=(8, 6), constrained_layout=True)
    ax.errorbar(
        centres,
        counts - bkg,
        yerr=errors,
        fmt="o",
        color="black",
        markersize=4,
        label="Dati $-$ fondo",
    )
    ax.axhline(0.0, ls="--", color="#0072B2", lw=2)
    ax.axvspan(SIG_LO, SIG_HI, color="grey", alpha=0.12)
    ax.set_xlabel(r"$m_{\gamma\gamma}$ [GeV]")
    ax.set_ylabel(f"Eventi $-$ fondo / {(M_HI - M_LO) / N_BINS:.1f} GeV")
    ax.set_title("Dopo: sottratto il fondo")
    ax.set_xlim(M_LO, M_HI)
    ax.legend()
    fig.savefig("gg_post_analysis.png", dpi=200, bbox_inches="tight")
    plt.close(fig)

    print("scritti gg_pre_analysis.png e gg_post_analysis.png")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    main(sys.argv[1:])
