use rand::rngs::StdRng;
use rand::{Rng, RngExt, SeedableRng};
use rand_distr::{Distribution, Exp, Normal};
use serde::Serialize;
use std::error::Error;
use std::f64::consts::PI;
use std::fs;

const N_SIGNAL: usize = 30_000;
const N_BACKGROUND: usize = 150_000;

#[derive(Debug, Serialize)]
struct Event {
    process: &'static str,
    electron_pt: f64,
    met: f64,
    delta_phi: f64,
    isolation: f64,
    transverse_mass: f64,
    tight_id: bool,
}

fn transverse_mass(electron_pt: f64, met: f64, delta_phi: f64) -> f64 {
    let mt_squared = 2.0 * electron_pt * met * (1.0 - delta_phi.cos());
    mt_squared.max(0.0).sqrt()
}

fn generate_signal<R: Rng + ?Sized>(
    rng: &mut R,
    pt_distribution: &Normal<f64>,
    met_distribution: &Normal<f64>,
    phi_smearing: &Normal<f64>,
    isolation_distribution: &Normal<f64>,
) -> Event {
    // Nel decadimento W -> e nu, elettrone e neutrino hanno tipicamente
    // momenti trasversi dell'ordine di metà della massa del W.
    let electron_pt = pt_distribution.sample(rng).max(5.0);
    let met = met_distribution.sample(rng).max(0.0);

    // Elettrone e neutrino sono approssimativamente opposti
    // nel piano trasverso.
    let delta_phi = (PI - phi_smearing.sample(rng).abs()).clamp(0.0, PI);

    // Un vero elettrone tende a essere isolato.
    let isolation = isolation_distribution.sample(rng).abs().clamp(0.0, 1.0);

    let tight_id = rng.random_bool(0.92);

    Event {
        process: "signal",
        electron_pt,
        met,
        delta_phi,
        isolation,
        transverse_mass: transverse_mass(electron_pt, met, delta_phi),
        tight_id,
    }
}

fn generate_background<R: Rng + ?Sized>(
    rng: &mut R,
    pt_distribution: &Exp<f64>,
    met_distribution: &Exp<f64>,
    isolation_distribution: &Exp<f64>,
) -> Event {
    // Per il fondo QCD-like, pT e MET sono prevalentemente bassi,
    // con code esponenziali.
    let electron_pt = 8.0 + pt_distribution.sample(rng);
    let met = met_distribution.sample(rng);

    // Nel fondo non imponiamo una correlazione particolare tra
    // il candidato elettrone e la MET.
    let delta_phi = rng.random_range(0.0..PI);

    // I jet che imitano elettroni tendono a essere meno isolati.
    let isolation = (0.03 + isolation_distribution.sample(rng)).clamp(0.0, 1.0);

    // Solo una piccola frazione supera l'identificazione tight.
    let tight_id = rng.random_bool(0.18);

    Event {
        process: "qcd",
        electron_pt,
        met,
        delta_phi,
        isolation,
        transverse_mass: transverse_mass(electron_pt, met, delta_phi),
        tight_id,
    }
}

fn main() -> Result<(), Box<dyn Error>> {
    fs::create_dir_all("output")?;

    // Seed fissato: la simulazione è riproducibile.
    let mut rng = StdRng::seed_from_u64(42);

    let signal_pt = Normal::new(40.0, 8.0)?;
    let signal_met = Normal::new(40.0, 10.0)?;
    let signal_phi_smearing = Normal::new(0.0, 0.35)?;
    let signal_isolation = Normal::new(0.04, 0.025)?;

    // Exp(lambda) ha media 1 / lambda.
    let background_pt = Exp::new(1.0 / 18.0)?;
    let background_met = Exp::new(1.0 / 14.0)?;
    let background_isolation = Exp::new(1.0 / 0.18)?;

    let mut writer = csv::Writer::from_path("output/events.csv")?;

    for _ in 0..N_SIGNAL {
        let event = generate_signal(
            &mut rng,
            &signal_pt,
            &signal_met,
            &signal_phi_smearing,
            &signal_isolation,
        );

        writer.serialize(event)?;
    }

    for _ in 0..N_BACKGROUND {
        let event = generate_background(
            &mut rng,
            &background_pt,
            &background_met,
            &background_isolation,
        );

        writer.serialize(event)?;
    }

    writer.flush()?;

    println!(
        "Generated {} signal events and {} background events.",
        N_SIGNAL, N_BACKGROUND
    );
    println!("Output written to output/events.csv");

    Ok(())
}
