# Toy Monte Carlo

This program generates an idealised sample of the two-body decay
$W \rightarrow e\nu$. The decay is isotropic in the $W$ rest frame, both
products are massless and the fixed input mass is $m_W = 80.4$ GeV. A
longitudinal boost with $\beta_z = 0.6$ is applied before calculating

```math
m_T = \sqrt{2p_T^e E_T^{\mathrm{miss}}(1-\cos\Delta\phi)}.
```

The result illustrates the Jacobian endpoint only. It is not an ATLAS or
detector-level simulation, and 80.4 GeV is an input rather than a fitted
measurement.

## Reproduce the result

The generator requires a Rust 2024 toolchain. The plotting step requires
Python 3.14 or later and [uv](https://docs.astral.sh/uv/).

```bash
cd poster/monte-carlo-simulation
cargo run --release -- --seed 42 --events 100000 --output output/mt_toy.csv
uv run python plot.py --input output/mt_toy.csv --output output/mt_toy.svg
```

The versioned outputs are the [60-bin CSV histogram](output/mt_toy.csv) and
the [vector plot](output/mt_toy.svg). The `density` column is a probability
density in GeV$^{-1}$, so `sum(density * bin_width)` is one.

Use `cargo run -- --help` and `uv run python plot.py --help` to inspect the
available options.

## Tests

```bash
cargo test --locked
```

The Rust tests cover argument parsing, four-vector invariants, conservation
laws, deterministic sampling and histogram normalisation.
