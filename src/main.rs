use clap::Parser as ClapParser;
use std::fs;
use std::path::PathBuf;
use std::process;

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

    let source = match fs::read_to_string(&cli.file) {
        Ok(s) => s,
        Err(e) => {
            eprintln!("error: could not read {}: {}", cli.file.display(), e);
            process::exit(1);
        }
    };

    match rlang::parser::parse(&source) {
        Ok(trace) => {
            if let Err(errors) = rlang::validator::validate(&trace) {
                for err in &errors {
                    eprintln!("{}", err);
                }
                process::exit(1);
            }

            if !cli.quiet && !cli.validate_only {
                if cli.ast {
                    println!("{}", serde_json::to_string_pretty(&trace).unwrap());
                } else {
                    println!("OK: {} phases, {} statements",
                        trace.phases.len(),
                        trace.phases.iter().map(|p| p.statements.len()).sum::<usize>());
                }
            }
        }
        Err(e) => {
            eprintln!("{}", e);
            process::exit(1);
        }
    }
}
