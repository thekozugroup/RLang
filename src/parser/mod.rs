pub mod expressions;
pub mod statements;
pub mod metadata;
pub mod types;
pub mod blocks;

use crate::ast::Trace;
use crate::errors::ParseError;

pub fn parse(_source: &str) -> Result<Trace, ParseError> {
    todo!("Parser implementation")
}
