use clap::Parser as ClapParser;
use std::fs;
use std::io::IsTerminal;
use std::path::PathBuf;
use std::process;

use rlang::errors::diagnostic::Diagnostic;

#[derive(ClapParser)]
#[command(name = "rlang", version, about = "RLang reasoning trace parser and validator")]
struct Cli {
    /// Path to .rl file to parse
    file: PathBuf,

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

fn main() {
    let cli = Cli::parse();
    let filename = cli.file.display().to_string();

    let source = match fs::read_to_string(&cli.file) {
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

            if cli.ast && !cli.validate_only {
                println!("{}", serde_json::to_string_pretty(&trace).unwrap());
            } else if !cli.quiet {
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
