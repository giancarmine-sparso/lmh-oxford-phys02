
## Introduction

One of the most promising areas for a future breakthrough in particle physics is the search for **charged-lepton flavour violation**. The Standard Model describes electrons, muons and tau particles as belonging to different lepton families, and transitions between these families are extremely suppressed in charged-particle decays.

The Mu3e experiment searches for the rare decay

$$
\mu^+ \rightarrow e^+e^-e^+.
$$

Observing this process at an experimentally accessible rate would be a clear sign that the Standard Model is incomplete. Mu3e is therefore not simply measuring a known phenomenon more precisely: it is searching for a process that could reveal entirely new particles or interactions.

## What does “flavour violation” mean?

Charged leptons come in three flavours:

$$
e, \qquad \mu, \qquad \tau.
$$

In the ordinary decay of a positive muon,

$$
\mu^+ \rightarrow e^+ + \nu_e + \bar{\nu}_\mu,
$$

the muon flavour is carried away by the muon antineutrino, while the electron neutrino accounts for the electron flavour produced in the decay.

Mu3e instead searches for

$$
\mu^+ \rightarrow e^+ e^- e^+.
$$

Since no neutrinos are produced, the initial muon flavour is converted entirely into electron flavour. This is called **charged-lepton flavour violation**.

Lepton flavour violation has already been observed in neutrino oscillations, but it has never been detected in the charged-lepton sector.

Neutrino masses make this decay technically possible because the neutrino flavour states are not identical to the neutrino mass states. Instead, each flavour state is a quantum mixture of particles with different masses. This mixing allows a muon to couple indirectly to an electron through loop processes involving virtual neutrinos and \(W\) bosons. If all neutrinos were massless or had exactly the same mass, the different contributions would cancel completely. Because their masses are slightly different, the cancellation is not exact, leaving a non-zero decay amplitude. However, since neutrino masses are extremely small, the remaining effect is so strongly suppressed that the predicted branching ratio is only about \(10^{-54}\).
## Why would this be almost unambiguous evidence of new physics?

In the original Standard Model, where neutrinos are massless, the decay

$$
\mu^+ \rightarrow e^+ e^- e^+
$$

is forbidden. When neutrino masses and mixing are included, the process becomes technically possible through loop diagrams, but with an extremely small predicted branching ratio:

$$
\mathrm{Br}(\mu^+ \rightarrow e^+ e^- e^+) \sim 10^{-54}.
$$

This suppression is caused by the tiny neutrino masses and GIM-like cancellations, making the process completely inaccessible experimentally.

Mu3e instead aims to reach sensitivities of about $10^{-15}$ in its first phase and eventually $10^{-16}$. Therefore, any observed signal could not be explained by known neutrino mixing and would require new particles or interactions.

Possible explanations include heavy neutrinos, new scalar or vector bosons, extended Higgs sectors, leptoquarks, supersymmetry, or other mechanisms related to the origin of lepton flavour and neutrino masses.

## How does Mu3e work?

Mu3e uses an intense beam of positive muons produced at the Paul Scherrer Institute. The muons are slowed down and stopped inside a thin double-cone target, where they decay.

The detector surrounds the target inside a magnetic field of approximately $1\,\mathrm{T}$. If the rare decay

$$
\mu^+ \rightarrow e^+e^-e^+
$$

occurs, the three charged particles follow curved trajectories through the detector.

Mu3e combines several detector systems:

- **ultra-thin silicon pixel sensors** reconstruct the trajectories and decay vertex;
- **scintillating fibres and tiles** measure when each particle crosses the detector;
- the **magnetic field** allows the particles' momenta and charges to be determined from the curvature of their tracks;
- a triggerless data-acquisition system records the detector data, which are reconstructed in real time using GPUs.

A candidate event must contain two positrons and one electron produced at the same time and from the same vertex. Their reconstructed total energy and momentum must also be consistent with the decay of a muon at rest.

These measurements allow Mu3e to distinguish a possible signal from ordinary muon decays and from accidental combinations of particles produced in separate events.
