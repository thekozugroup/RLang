pub mod phases;
pub mod metadata;
pub mod bounds;
pub mod resources;
pub mod types;

use crate::ast::Trace;
use crate::errors::ValidationError;

pub fn validate(_trace: &Trace) -> Result<(), Vec<ValidationError>> {
    todo!("Validator implementation")
}
