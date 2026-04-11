pub mod expressions;
pub mod statements;
pub mod metadata;
pub mod types;
pub mod blocks;

use pest::Parser;

use crate::ast::Trace;
use crate::errors::ParseError;
use crate::grammar::{RLangParser, Rule};

/// Parse an RLang source string into a typed AST Trace.
pub fn parse(source: &str) -> Result<Trace, ParseError> {
    let pairs = RLangParser::parse(Rule::trace, source).map_err(|e| {
        let (line, col) = match e.line_col {
            pest::error::LineColLocation::Pos((l, c)) => (l, c),
            pest::error::LineColLocation::Span((l, c), _) => (l, c),
        };
        ParseError::Syntax {
            line,
            col,
            message: format!("{}", e),
        }
    })?;

    let trace_pair = pairs.into_iter().next().ok_or_else(|| ParseError::Syntax {
        line: 0,
        col: 0,
        message: "no trace found in input".to_string(),
    })?;

    blocks::parse_trace(trace_pair)
}
