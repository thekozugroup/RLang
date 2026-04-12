use clap::{Parser as ClapParser, Subcommand};
use std::fs;
use std::io::IsTerminal;
use std::path::PathBuf;
use std::process;

use rlang::errors::diagnostic::Diagnostic;

#[derive(ClapParser)]
#[command(name = "rlang", version, about = "RLang reasoning trace parser and validator")]
struct Cli {
    #[command(subcommand)]
    command: Option<Commands>,

    /// Path to .rl file to parse (when no subcommand is given)
    file: Option<PathBuf>,

    /// Output parsed AST as JSON
    #[arg(long)]
    ast: bool,

    /// Only validate, don't output AST
    #[arg(long)]
    validate_only: bool,

    /// Suppress output on success
    #[arg(short, long)]
    quiet: bool,
}

#[derive(Subcommand)]
enum Commands {
    /// Generate training data for fine-tuning
    Generate {
        /// Number of examples to generate
        #[arg(long, default_value = "100")]
        count: usize,

        /// Output format: jsonl or sharegpt
        #[arg(long, default_value = "jsonl")]
        format: String,

        /// Output file path (defaults to stdout)
        #[arg(long, short)]
        output: Option<PathBuf>,

        /// Comma-separated list of categories to include
        /// (causal, risk, evidence, goal, delegation, conflict, tool, correction, memory, planning)
        #[arg(long)]
        categories: Option<String>,

        /// Random seed for reproducibility
        #[arg(long)]
        seed: Option<u64>,
    },
}

fn main() {
    let cli = Cli::parse();

    match cli.command {
        Some(Commands::Generate {
            count,
            format,
            output,
            categories,
            seed,
        }) => {
            run_generate(count, &format, output, categories, seed);
        }
        None => {
            // Original behavior: parse a file
            let file = match cli.file {
                Some(f) => f,
                None => {
                    eprintln!("\x1b[1;31merror\x1b[0m: no input file provided");
                    eprintln!("Usage: rlang <FILE> or rlang generate --count 100");
                    process::exit(1);
                }
            };
            run_parse(&file, cli.ast, cli.validate_only, cli.quiet);
        }
    }
}

fn run_parse(file: &PathBuf, ast: bool, validate_only: bool, quiet: bool) {
    let filename = file.display().to_string();

    let source = match fs::read_to_string(file) {
        Ok(s) => s,
        Err(e) => {
            eprintln!(
                "\x1b[1;31merror\x1b[0m\x1b[1m: could not read `{}`\x1b[0m: {}",
                filename, e
            );
            process::exit(1);
        }
    };

    let use_color = std::io::stderr().is_terminal();
    let diag = Diagnostic::new(&source, &filename);

    match rlang::parser::parse(&source) {
        Ok(trace) => {
            if let Err(errors) = rlang::validator::validate(&trace) {
                for err in &errors {
                    if use_color {
                        eprintln!("{}", diag.format_validation_error(err));
                    } else {
                        eprintln!("{}", diag.format_validation_error_plain(err));
                    }
                    eprintln!();
                }
                let count = errors.len();
                eprintln!(
                    "\x1b[1;31merror\x1b[0m: aborting due to {} validation error{}",
                    count,
                    if count == 1 { "" } else { "s" }
                );
                process::exit(1);
            }

            if ast && !validate_only {
                println!("{}", serde_json::to_string_pretty(&trace).unwrap());
            } else if !quiet {
                let phase_count = trace.phases.len();
                let stmt_count: usize = trace.phases.iter().map(|p| p.statements.len()).sum();
                println!(
                    "\x1b[1;32mOK\x1b[0m: {} phase{}, {} statement{}",
                    phase_count,
                    if phase_count == 1 { "" } else { "s" },
                    stmt_count,
                    if stmt_count == 1 { "" } else { "s" },
                );
            }
        }
        Err(e) => {
            if use_color {
                eprintln!("{}", diag.format_parse_error(&e));
            } else {
                eprintln!("{}", diag.format_parse_error_plain(&e));
            }
            eprintln!();
            eprintln!("\x1b[1;31merror\x1b[0m: aborting due to parse error");
            process::exit(1);
        }
    }
}

fn run_generate(
    count: usize,
    format: &str,
    output: Option<PathBuf>,
    categories_str: Option<String>,
    seed: Option<u64>,
) {
    use rlang::training::{self, Category};

    // Parse categories
    let categories: Vec<Category> = match categories_str {
        Some(ref s) => {
            let mut cats = Vec::new();
            for name in s.split(',') {
                match Category::from_str(name.trim()) {
                    Some(c) => cats.push(c),
                    None => {
                        eprintln!(
                            "\x1b[1;31merror\x1b[0m: unknown category '{}'. \
                             Valid categories: causal, risk, evidence, goal, delegation, \
                             conflict, tool, correction, memory, planning",
                            name.trim()
                        );
                        process::exit(1);
                    }
                }
            }
            cats
        }
        None => Category::all().to_vec(),
    };

    // Generate examples
    let examples = match seed {
        Some(s) => training::generate_batch_seeded(count, &categories, s),
        None => training::generate_batch(count, &categories),
    };

    if examples.is_empty() {
        eprintln!("\x1b[1;33mwarning\x1b[0m: no valid examples generated");
        process::exit(1);
    }

    // Format output
    let output_str = match format {
        "jsonl" => training::to_jsonl(&examples),
        "sharegpt" => training::to_sharegpt(&examples),
        other => {
            eprintln!(
                "\x1b[1;31merror\x1b[0m: unknown format '{}'. Valid formats: jsonl, sharegpt",
                other
            );
            process::exit(1);
        }
    };

    // Write output
    match output {
        Some(path) => {
            if let Err(e) = fs::write(&path, &output_str) {
                eprintln!(
                    "\x1b[1;31merror\x1b[0m: could not write to `{}`: {}",
                    path.display(),
                    e
                );
                process::exit(1);
            }
            eprintln!(
                "\x1b[1;32mOK\x1b[0m: generated {} examples in {} format -> {}",
                examples.len(),
                format,
                path.display()
            );
        }
        None => {
            println!("{}", output_str);
        }
    }
}
