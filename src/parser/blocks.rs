use pest::iterators::Pair;

use crate::ast::common::Statement;
use crate::ast::phases::{Phase, PhaseBlock, ReasoningMode, Trace};
use crate::errors::ParseError;
use crate::grammar::Rule;

use super::statements::parse_statement;

/// Parse the top-level trace (the root rule)
pub fn parse_trace(pair: Pair<Rule>) -> Result<Trace, ParseError> {
    let mut phases = Vec::new();

    for child in pair.into_inner() {
        match child.as_rule() {
            Rule::phase_block => {
                phases.push(parse_phase_block(child)?);
            }
            Rule::EOI => {} // End of input
            _ => {}
        }
    }

    Ok(Trace {
        phases,
        span: None,
    })
}

fn parse_phase_block(pair: Pair<Rule>) -> Result<PhaseBlock, ParseError> {
    let mut inner = pair.into_inner();

    // phase_attr: #[phase(Name)]
    let attr_pair = inner.next().unwrap();
    let phase = parse_phase_attr(attr_pair)?;

    // impl_block | bare_block
    let block_pair = inner.next().unwrap();
    let (impl_mode, statements) = match block_pair.as_rule() {
        Rule::impl_block => parse_impl_block(block_pair)?,
        Rule::bare_block => (None, parse_bare_block(block_pair)?),
        _ => {
            let (line, col) = block_pair.as_span().start_pos().line_col();
            return Err(ParseError::Syntax {
                line,
                col,
                message: format!("expected impl_block or bare_block, got {:?}", block_pair.as_rule()),
            });
        }
    };

    Ok(PhaseBlock {
        phase,
        impl_mode,
        statements,
        span: None,
    })
}

fn parse_phase_attr(pair: Pair<Rule>) -> Result<Phase, ParseError> {
    let name_pair = pair.into_inner().next().unwrap();
    match name_pair.as_str() {
        "Frame" => Ok(Phase::Frame),
        "Explore" => Ok(Phase::Explore),
        "Verify" => Ok(Phase::Verify),
        "Decide" => Ok(Phase::Decide),
        other => {
            let (line, col) = name_pair.as_span().start_pos().line_col();
            Err(ParseError::Syntax {
                line,
                col,
                message: format!("unknown phase: {}", other),
            })
        }
    }
}

fn parse_impl_block(pair: Pair<Rule>) -> Result<(Option<ReasoningMode>, Vec<Statement>), ParseError> {
    let mut inner = pair.into_inner();

    // reasoning_mode
    let mode_pair = inner.next().unwrap();
    let mode = match mode_pair.as_str() {
        "Deductive" => ReasoningMode::Deductive,
        "Abductive" => ReasoningMode::Abductive,
        "Analogical" => ReasoningMode::Analogical,
        other => {
            let (line, col) = mode_pair.as_span().start_pos().line_col();
            return Err(ParseError::Syntax {
                line,
                col,
                message: format!("unknown reasoning mode: {}", other),
            });
        }
    };

    // statements
    let mut statements = Vec::new();
    for child in inner {
        if child.as_rule() == Rule::statement {
            statements.push(parse_statement(child)?);
        }
    }

    Ok((Some(mode), statements))
}

fn parse_bare_block(pair: Pair<Rule>) -> Result<Vec<Statement>, ParseError> {
    let mut statements = Vec::new();
    for child in pair.into_inner() {
        if child.as_rule() == Rule::statement {
            statements.push(parse_statement(child)?);
        }
    }
    Ok(statements)
}
