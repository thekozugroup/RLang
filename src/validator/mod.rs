pub mod phases;
pub mod metadata;
pub mod bounds;
pub mod resources;
pub mod types;

use crate::ast::phases::Trace;
use crate::errors::ValidationError;

pub fn validate(trace: &Trace) -> Result<(), Vec<ValidationError>> {
    let mut all_errors = Vec::new();

    if let Err(errors) = phases::validate_phases(trace) {
        all_errors.extend(errors);
    }

    if let Err(errors) = metadata::validate_metadata(trace) {
        all_errors.extend(errors);
    }

    // Future: bounds, resources, types validators

    if all_errors.is_empty() {
        Ok(())
    } else {
        Err(all_errors)
    }
}
