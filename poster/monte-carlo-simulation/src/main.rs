use rand::{Rng, RngExt, SeedableRng, rngs::StdRng};
use std::env;
use std::error::Error;
use std::f64::consts::{PI, TAU};
use std::fmt;
use std::fs::{self, File};
use std::io::{BufWriter, Write};
use std::path::{Path, PathBuf};
use std::process;

const W_MASS_GEV: f64 = 80.4;
const W_BETA_Z: f64 = 0.6;
const DEFAULT_SEED: u64 = 42;
const DEFAULT_EVENTS: usize = 100_000;
const DEFAULT_OUTPUT: &str = "output/mt_toy.csv";
const NUMERICAL_TOLERANCE: f64 = 1.0e-10;
const HISTOGRAM_AREA_TOLERANCE: f64 = 1.0e-12;
const STATISTICAL_WARNING_SIGMA: f64 = 5.0;
const HISTOGRAM_MIN_GEV: f64 = 0.0;
const HISTOGRAM_MAX_GEV: f64 = 90.0;
const HISTOGRAM_BINS: usize = 60;

const HELP_TEXT: &str = "Idealised W -> e nu kinematic toy

Usage:
  monte-carlo-simulation [--seed <u64>] [--events <usize>] [--output <path>]
  monte-carlo-simulation --help

Options:
  --seed <u64>       Random-number seed [default: 42]
  --events <usize>   Number of events, greater than zero [default: 100000]
  --output <path>    Histogram CSV output path [default: output/mt_toy.csv]
  --help             Print this help message
";

#[derive(Debug, Clone, PartialEq, Eq)]
struct CliConfig {
    seed: u64,
    events: usize,
    output: PathBuf,
}

impl Default for CliConfig {
    fn default() -> Self {
        Self {
            seed: DEFAULT_SEED,
            events: DEFAULT_EVENTS,
            output: PathBuf::from(DEFAULT_OUTPUT),
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
enum CliAction {
    Run(CliConfig),
    Help,
}

#[derive(Debug)]
struct ToyError(String);

impl fmt::Display for ToyError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter.write_str(&self.0)
    }
}

impl Error for ToyError {}

#[derive(Debug, Clone, Copy)]
struct FourVector {
    energy: f64,
    px: f64,
    py: f64,
    pz: f64,
}

impl FourVector {
    fn momentum_squared(&self) -> f64 {
        self.px * self.px + self.py * self.py + self.pz * self.pz
    }

    fn mass_squared(&self) -> f64 {
        self.energy * self.energy - self.momentum_squared()
    }

    fn pt(&self) -> f64 {
        (self.px * self.px + self.py * self.py).sqrt()
    }

    fn add(&self, other: &FourVector) -> FourVector {
        FourVector {
            energy: self.energy + other.energy,
            px: self.px + other.px,
            py: self.py + other.py,
            pz: self.pz + other.pz,
        }
    }

    // Boost di Lorentz lungo l'asse z: px e py non cambiano.
    fn boost_z(&self, beta: f64) -> FourVector {
        assert!(
            beta.abs() < 1.0,
            "The boost velocity must satisfy |beta| < 1"
        );

        let gamma = 1.0 / (1.0 - beta * beta).sqrt();

        FourVector {
            energy: gamma * (self.energy + beta * self.pz),
            px: self.px,
            py: self.py,
            pz: gamma * (self.pz + beta * self.energy),
        }
    }
}

#[derive(Debug, Clone, Copy)]
struct DecayEvent {
    cos_theta: f64,
    electron_rest: FourVector,
    neutrino_rest: FourVector,
}

#[derive(Debug, Clone, Copy)]
struct SimulationSummary {
    events: usize,
    mean_cos_theta: f64,
    mean_cos_theta_squared: f64,
    maximum_transverse_mass: f64,
    maximum_electron_mass_squared_error: f64,
    maximum_neutrino_mass_squared_error: f64,
    maximum_energy_error: f64,
    maximum_momentum_error: f64,
    maximum_mass_error: f64,
    maximum_lab_w_energy_error: f64,
    maximum_lab_w_pz_error: f64,
    maximum_lab_w_mass_error: f64,
    maximum_electron_pt_change: f64,
}

#[derive(Debug, Clone)]
struct SimulationResult {
    transverse_masses: Vec<f64>,
    summary: SimulationSummary,
}

#[derive(Debug, Clone, Copy)]
struct HistogramBin {
    low: f64,
    high: f64,
    center: f64,
    density: f64,
    count: usize,
}

#[derive(Debug, Clone)]
struct NormalisedHistogram {
    bins: Vec<HistogramBin>,
    bin_width: f64,
    area: f64,
}

fn parse_cli<I>(arguments: I) -> Result<CliAction, String>
where
    I: IntoIterator<Item = String>,
{
    let arguments: Vec<String> = arguments.into_iter().collect();
    if arguments.iter().any(|argument| argument == "--help") {
        return Ok(CliAction::Help);
    }

    let mut config = CliConfig::default();
    let mut seed_seen = false;
    let mut events_seen = false;
    let mut output_seen = false;
    let mut arguments = arguments.into_iter();

    while let Some(argument) = arguments.next() {
        match argument.as_str() {
            "--seed" => {
                if seed_seen {
                    return Err("--seed may only be specified once".to_string());
                }
                seed_seen = true;
                let value = next_cli_value(&mut arguments, "--seed")?;
                config.seed = value
                    .parse::<u64>()
                    .map_err(|_| format!("invalid value for --seed: '{value}' (expected u64)"))?;
            }
            "--events" => {
                if events_seen {
                    return Err("--events may only be specified once".to_string());
                }
                events_seen = true;
                let value = next_cli_value(&mut arguments, "--events")?;
                config.events = value.parse::<usize>().map_err(|_| {
                    format!("invalid value for --events: '{value}' (expected usize)")
                })?;
                if config.events == 0 {
                    return Err("--events must be greater than zero".to_string());
                }
            }
            "--output" => {
                if output_seen {
                    return Err("--output may only be specified once".to_string());
                }
                output_seen = true;
                let value = next_cli_value(&mut arguments, "--output")?;
                if value.is_empty() {
                    return Err("--output must not be empty".to_string());
                }
                config.output = PathBuf::from(value);
            }
            _ if argument.starts_with('-') => {
                return Err(format!("unknown option: '{argument}'"));
            }
            _ => return Err(format!("unexpected positional argument: '{argument}'")),
        }
    }

    let has_csv_extension = config
        .output
        .extension()
        .and_then(|extension| extension.to_str())
        .is_some_and(|extension| extension.eq_ignore_ascii_case("csv"));
    if !has_csv_extension {
        return Err("--output must name a CSV file with a .csv extension".to_string());
    }

    Ok(CliAction::Run(config))
}

fn next_cli_value(
    arguments: &mut impl Iterator<Item = String>,
    option: &str,
) -> Result<String, String> {
    let value = arguments
        .next()
        .ok_or_else(|| format!("missing value for {option}"))?;
    if value.starts_with("--") {
        return Err(format!("missing value for {option}"));
    }
    Ok(value)
}

fn decay_from_angles(cos_theta: f64, phi: f64) -> DecayEvent {
    let particle_momentum = W_MASS_GEV / 2.0;
    let sin_theta = (1.0 - cos_theta * cos_theta).max(0.0).sqrt();

    // Impulso dell'elettrone nel sistema di riposo del W.
    let electron_px = particle_momentum * sin_theta * phi.cos();
    let electron_py = particle_momentum * sin_theta * phi.sin();
    let electron_pz = particle_momentum * cos_theta;

    let electron_rest = FourVector {
        energy: particle_momentum,
        px: electron_px,
        py: electron_py,
        pz: electron_pz,
    };

    let neutrino_rest = FourVector {
        energy: particle_momentum,
        px: -electron_px,
        py: -electron_py,
        pz: -electron_pz,
    };

    DecayEvent {
        cos_theta,
        electron_rest,
        neutrino_rest,
    }
}

fn generate_event<R: Rng + ?Sized>(rng: &mut R) -> DecayEvent {
    let cos_theta = rng.random_range(-1.0..=1.0);
    let phi = rng.random_range(0.0..TAU);
    decay_from_angles(cos_theta, phi)
}

fn transverse_mass(electron_pt: f64, missing_et: f64, delta_phi: f64) -> f64 {
    let mass_squared = 2.0 * electron_pt * missing_et * (1.0 - delta_phi.cos());
    mass_squared.max(0.0).sqrt()
}

fn simulate(seed: u64, events: usize) -> Result<SimulationResult, ToyError> {
    if events == 0 {
        return Err(ToyError(
            "the simulation requires at least one event".to_string(),
        ));
    }

    let mut rng = StdRng::seed_from_u64(seed);
    let mut transverse_masses = Vec::with_capacity(events);
    let expected_w_lab = FourVector {
        energy: W_MASS_GEV,
        px: 0.0,
        py: 0.0,
        pz: 0.0,
    }
    .boost_z(W_BETA_Z);

    let mut sum_cos_theta = 0.0;
    let mut sum_cos_theta_squared = 0.0;
    let mut maximum_transverse_mass = 0.0_f64;
    let mut maximum_electron_mass_squared_error = 0.0_f64;
    let mut maximum_neutrino_mass_squared_error = 0.0_f64;
    let mut maximum_energy_error = 0.0_f64;
    let mut maximum_momentum_error = 0.0_f64;
    let mut maximum_mass_error = 0.0_f64;
    let mut maximum_lab_w_energy_error = 0.0_f64;
    let mut maximum_lab_w_pz_error = 0.0_f64;
    let mut maximum_lab_w_mass_error = 0.0_f64;
    let mut maximum_electron_pt_change = 0.0_f64;

    for _ in 0..events {
        let event = generate_event(&mut rng);
        let electron_pt_rest = event.electron_rest.pt();
        let missing_et = event.neutrino_rest.pt();
        let event_transverse_mass = transverse_mass(electron_pt_rest, missing_et, PI);

        if !event_transverse_mass.is_finite()
            || event_transverse_mass > W_MASS_GEV + NUMERICAL_TOLERANCE
        {
            return Err(ToyError(format!(
                "transverse mass exceeds the input W mass: {event_transverse_mass:.12} GeV"
            )));
        }

        transverse_masses.push(event_transverse_mass);
        sum_cos_theta += event.cos_theta;
        sum_cos_theta_squared += event.cos_theta * event.cos_theta;
        maximum_transverse_mass = maximum_transverse_mass.max(event_transverse_mass);

        let reconstructed_w = event.electron_rest.add(&event.neutrino_rest);
        let reconstructed_w_mass = reconstructed_w.mass_squared().max(0.0).sqrt();
        let electron_mass_squared_error = event.electron_rest.mass_squared().abs();
        let neutrino_mass_squared_error = event.neutrino_rest.mass_squared().abs();

        let electron_lab = event.electron_rest.boost_z(W_BETA_Z);
        let neutrino_lab = event.neutrino_rest.boost_z(W_BETA_Z);
        let reconstructed_w_lab = electron_lab.add(&neutrino_lab);
        let reconstructed_w_lab_mass = reconstructed_w_lab.mass_squared().max(0.0).sqrt();
        let electron_pt_change = (electron_lab.pt() - electron_pt_rest).abs();

        maximum_electron_mass_squared_error =
            maximum_electron_mass_squared_error.max(electron_mass_squared_error);
        maximum_neutrino_mass_squared_error =
            maximum_neutrino_mass_squared_error.max(neutrino_mass_squared_error);
        maximum_energy_error =
            maximum_energy_error.max((reconstructed_w.energy - W_MASS_GEV).abs());
        maximum_momentum_error =
            maximum_momentum_error.max(reconstructed_w.momentum_squared().sqrt());
        maximum_mass_error = maximum_mass_error.max((reconstructed_w_mass - W_MASS_GEV).abs());
        maximum_lab_w_energy_error = maximum_lab_w_energy_error
            .max((reconstructed_w_lab.energy - expected_w_lab.energy).abs());
        maximum_lab_w_pz_error =
            maximum_lab_w_pz_error.max((reconstructed_w_lab.pz - expected_w_lab.pz).abs());
        maximum_lab_w_mass_error =
            maximum_lab_w_mass_error.max((reconstructed_w_lab_mass - W_MASS_GEV).abs());
        maximum_electron_pt_change = maximum_electron_pt_change.max(electron_pt_change);
    }

    let number_of_events = events as f64;
    let summary = SimulationSummary {
        events,
        mean_cos_theta: sum_cos_theta / number_of_events,
        mean_cos_theta_squared: sum_cos_theta_squared / number_of_events,
        maximum_transverse_mass,
        maximum_electron_mass_squared_error,
        maximum_neutrino_mass_squared_error,
        maximum_energy_error,
        maximum_momentum_error,
        maximum_mass_error,
        maximum_lab_w_energy_error,
        maximum_lab_w_pz_error,
        maximum_lab_w_mass_error,
        maximum_electron_pt_change,
    };

    validate_summary(&summary)?;

    Ok(SimulationResult {
        transverse_masses,
        summary,
    })
}

fn validate_summary(summary: &SimulationSummary) -> Result<(), ToyError> {
    check_numerical_error(
        "electron mass-squared error",
        summary.maximum_electron_mass_squared_error,
    )?;
    check_numerical_error(
        "neutrino mass-squared error",
        summary.maximum_neutrino_mass_squared_error,
    )?;
    check_numerical_error("rest-frame energy error", summary.maximum_energy_error)?;
    check_numerical_error("rest-frame momentum error", summary.maximum_momentum_error)?;
    check_numerical_error("rest-frame W mass error", summary.maximum_mass_error)?;
    check_numerical_error(
        "lab-frame W energy error",
        summary.maximum_lab_w_energy_error,
    )?;
    check_numerical_error("lab-frame W pz error", summary.maximum_lab_w_pz_error)?;
    check_numerical_error("lab-frame W mass error", summary.maximum_lab_w_mass_error)?;
    check_numerical_error(
        "electron transverse-momentum change",
        summary.maximum_electron_pt_change,
    )?;

    if !summary.maximum_transverse_mass.is_finite()
        || summary.maximum_transverse_mass > W_MASS_GEV + NUMERICAL_TOLERANCE
    {
        return Err(ToyError(format!(
            "maximum transverse mass is inconsistent with the endpoint: {:.12} GeV",
            summary.maximum_transverse_mass
        )));
    }

    Ok(())
}

fn check_numerical_error(label: &str, value: f64) -> Result<(), ToyError> {
    if !value.is_finite() || value > NUMERICAL_TOLERANCE {
        return Err(ToyError(format!(
            "{label} exceeds the numerical tolerance: {value:.3e}"
        )));
    }
    Ok(())
}

fn build_histogram(values: &[f64]) -> Result<NormalisedHistogram, ToyError> {
    if values.is_empty() {
        return Err(ToyError(
            "cannot build a histogram from an empty sample".to_string(),
        ));
    }

    let bin_width = (HISTOGRAM_MAX_GEV - HISTOGRAM_MIN_GEV) / HISTOGRAM_BINS as f64;
    let mut counts = [0_usize; HISTOGRAM_BINS];

    for &value in values {
        if !value.is_finite() || !(HISTOGRAM_MIN_GEV..=HISTOGRAM_MAX_GEV).contains(&value) {
            return Err(ToyError(format!(
                "transverse mass outside the histogram range: {value}"
            )));
        }

        let index = if value == HISTOGRAM_MAX_GEV {
            HISTOGRAM_BINS - 1
        } else {
            ((value - HISTOGRAM_MIN_GEV) / bin_width).floor() as usize
        };
        counts[index] += 1;
    }

    let total_count: usize = counts.iter().sum();
    if total_count != values.len() {
        return Err(ToyError(
            "histogram counts do not match the simulated events".to_string(),
        ));
    }

    let normalisation = values.len() as f64 * bin_width;
    let bins: Vec<HistogramBin> = counts
        .into_iter()
        .enumerate()
        .map(|(index, count)| {
            let low = HISTOGRAM_MIN_GEV + index as f64 * bin_width;
            let high = low + bin_width;
            HistogramBin {
                low,
                high,
                center: 0.5 * (low + high),
                density: count as f64 / normalisation,
                count,
            }
        })
        .collect();
    let area: f64 = bins.iter().map(|bin| bin.density * bin_width).sum();

    if !area.is_finite() || (area - 1.0).abs() > HISTOGRAM_AREA_TOLERANCE {
        return Err(ToyError(format!(
            "normalised histogram area is {area:.15}, expected 1"
        )));
    }

    Ok(NormalisedHistogram {
        bins,
        bin_width,
        area,
    })
}

fn write_csv(histogram: &NormalisedHistogram, output_path: &Path) -> Result<(), Box<dyn Error>> {
    let file = File::create(output_path)?;
    let mut writer = BufWriter::new(file);
    writeln!(writer, "bin_low,bin_high,bin_center,density,count")?;

    for bin in &histogram.bins {
        writeln!(
            writer,
            "{:.6},{:.6},{:.6},{:.15},{}",
            bin.low, bin.high, bin.center, bin.density, bin.count
        )?;
    }

    writer.flush()?;
    Ok(())
}

fn create_output_directory(output_path: &Path) -> Result<(), Box<dyn Error>> {
    if let Some(parent) = output_path.parent()
        && !parent.as_os_str().is_empty()
    {
        fs::create_dir_all(parent)?;
    }
    Ok(())
}

fn print_summary(summary: &SimulationSummary) {
    let number_of_events = summary.events as f64;
    let cos_theta_standard_error = (1.0 / (3.0 * number_of_events)).sqrt();
    let cos_theta_squared_standard_error = (4.0 / (45.0 * number_of_events)).sqrt();
    let cos_theta_z_score = summary.mean_cos_theta / cos_theta_standard_error;
    let cos_theta_squared_z_score =
        (summary.mean_cos_theta_squared - 1.0 / 3.0) / cos_theta_squared_standard_error;

    println!();
    println!(
        "mean(cos(theta))           = {:.6}  (expected 0, z={cos_theta_z_score:.2})",
        summary.mean_cos_theta
    );
    println!(
        "mean(cos²(theta))          = {:.6}  (expected 1/3, z={cos_theta_squared_z_score:.2})",
        summary.mean_cos_theta_squared
    );
    println!(
        "maximum mT                 = {:.6} GeV",
        summary.maximum_transverse_mass
    );
    println!(
        "maximum electron m² error  = {:.3e} GeV²",
        summary.maximum_electron_mass_squared_error
    );
    println!(
        "maximum neutrino m² error  = {:.3e} GeV²",
        summary.maximum_neutrino_mass_squared_error
    );
    println!(
        "maximum energy error       = {:.3e} GeV",
        summary.maximum_energy_error
    );
    println!(
        "maximum momentum error     = {:.3e} GeV",
        summary.maximum_momentum_error
    );
    println!(
        "maximum W mass error       = {:.3e} GeV",
        summary.maximum_mass_error
    );
    println!(
        "maximum lab W energy error = {:.3e} GeV",
        summary.maximum_lab_w_energy_error
    );
    println!(
        "maximum lab W pz error     = {:.3e} GeV",
        summary.maximum_lab_w_pz_error
    );
    println!(
        "maximum lab W mass error   = {:.3e} GeV",
        summary.maximum_lab_w_mass_error
    );
    println!(
        "maximum electron pT change = {:.3e} GeV",
        summary.maximum_electron_pt_change
    );

    if cos_theta_z_score.abs() > STATISTICAL_WARNING_SIGMA {
        eprintln!(
            "warning: mean(cos(theta)) is more than {STATISTICAL_WARNING_SIGMA:.0} standard errors from zero"
        );
    }
    if cos_theta_squared_z_score.abs() > STATISTICAL_WARNING_SIGMA {
        eprintln!(
            "warning: mean(cos²(theta)) is more than {STATISTICAL_WARNING_SIGMA:.0} standard errors from 1/3"
        );
    }
}

fn run(config: &CliConfig) -> Result<(), Box<dyn Error>> {
    println!("Seed: {}", config.seed);
    println!("Events: {}", config.events);
    println!("Input W mass: {W_MASS_GEV:.1} GeV");
    println!("Histogram output: {}", config.output.display());

    let simulation = simulate(config.seed, config.events)?;
    let histogram = build_histogram(&simulation.transverse_masses)?;

    create_output_directory(&config.output)?;
    write_csv(&histogram, &config.output)?;

    print_summary(&simulation.summary);
    println!(
        "histogram bin width        = {:.6} GeV",
        histogram.bin_width
    );
    println!("normalised histogram area = {:.12}", histogram.area);
    println!("CSV written to: {}", config.output.display());

    Ok(())
}

fn main() {
    match parse_cli(env::args().skip(1)) {
        Ok(CliAction::Help) => print!("{HELP_TEXT}"),
        Ok(CliAction::Run(config)) => {
            if let Err(error) = run(&config) {
                eprintln!("error: {error}");
                process::exit(1);
            }
        }
        Err(error) => {
            eprintln!("error: {error}");
            eprintln!("Try '--help' for usage information.");
            process::exit(2);
        }
    }
}
