use crate::ast::common::Statement;
use crate::ast::phases::Trace;
use crate::errors::ValidationError;

pub fn validate_metadata(trace: &Trace) -> Result<(), Vec<ValidationError>> {
    let mut errors = Vec::new();

    for block in &trace.phases {
        for stmt in &block.statements {
            check_statement_metadata(stmt, &mut errors);
        }
    }

    if errors.is_empty() {
        Ok(())
    } else {
        Err(errors)
    }
}

fn check_statement_metadata(stmt: &Statement, errors: &mut Vec<ValidationError>) {
    match stmt {
        Statement::Let { metadata, name, .. } => {
            // Let bindings for beliefs should have confidence
            if let Some(meta) = metadata {
                if meta.confidence.is_none() {
                    errors.push(ValidationError::Metadata {
                        message: format!(
                            "let binding '{}' has metadata but missing required confidence (p:) field",
                            name.0
                        ),
                    });
                }
            }
            // Note: let bindings without metadata (e.g., evidence blocks) are OK
        }
        _ => {}
    }
}
