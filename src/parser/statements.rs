use pest::iterators::Pair;

use crate::ast::common::*;
use crate::errors::ParseError;
use crate::grammar::Rule;

use super::expressions::parse_expr;
use super::metadata::parse_metadata;
use super::types::parse_type_annotation;

/// Parse a single statement
pub fn parse_statement(pair: Pair<Rule>) -> Result<Statement, ParseError> {
    let span = pair.as_span();
    let (line, col) = span.start_pos().line_col();

    let inner = pair.into_inner().next().ok_or_else(|| ParseError::Syntax {
        line,
        col,
        message: "empty statement".to_string(),
    })?;

    match inner.as_rule() {
        Rule::let_binding => parse_let_binding(inner),
        Rule::assertion => parse_assertion(inner),
        Rule::pipe_chain_stmt => parse_pipe_chain_stmt(inner),
        Rule::match_expr_stmt => parse_match_expr_stmt(inner),
        _ => Err(ParseError::Syntax {
            line,
            col,
            message: format!("unexpected statement rule: {:?}", inner.as_rule()),
        }),
    }
}

fn parse_let_binding(pair: Pair<Rule>) -> Result<Statement, ParseError> {
    let mut inner = pair.into_inner();

    // First child is the identifier
    let name = Ident(inner.next().unwrap().as_str().to_string());

    // Consume remaining children to find type annotation, value expr, and metadata
    let mut type_ann = None;
    let mut value = None;
    let mut metadata = None;

    for child in inner {
        match child.as_rule() {
            Rule::type_annotation => {
                type_ann = Some(parse_type_annotation(child)?);
            }
            Rule::expr => {
                value = Some(parse_expr(child)?);
            }
            Rule::metadata => {
                metadata = Some(parse_metadata(child)?);
            }
            _ => {}
        }
    }

    let value = value.ok_or_else(|| {
        ParseError::Syntax {
            line: 0,
            col: 0,
            message: "let binding missing value expression".to_string(),
        }
    })?;

    Ok(Statement::Let {
        name,
        type_ann,
        value,
        metadata,
        span: None,
    })
}

fn parse_assertion(pair: Pair<Rule>) -> Result<Statement, ParseError> {
    let mut inner = pair.into_inner();

    // assertion_kw
    let kw_pair = inner.next().unwrap();
    let kind = match kw_pair.as_str() {
        "assert" => AssertionKind::Assert,
        "hedge" => AssertionKind::Hedge,
        "suspend" => AssertionKind::Suspend,
        "reject" => AssertionKind::Reject,
        "emit" => AssertionKind::Emit,
        other => {
            let (line, col) = kw_pair.as_span().start_pos().line_col();
            return Err(ParseError::Syntax {
                line,
                col,
                message: format!("unknown assertion keyword: {}", other),
            });
        }
    };

    // arg_list
    let mut args = vec![];
    let mut metadata = None;

    for child in inner {
        match child.as_rule() {
            Rule::arg_list => {
                for arg_pair in child.into_inner() {
                    args.push(parse_expr(arg_pair)?);
                }
            }
            Rule::metadata => {
                metadata = Some(parse_metadata(child)?);
            }
            _ => {}
        }
    }

    Ok(Statement::Assertion {
        kind,
        args,
        metadata,
        span: None,
    })
}

fn parse_pipe_chain_stmt(pair: Pair<Rule>) -> Result<Statement, ParseError> {
    // pipe_chain_stmt = { pipe_chain ~ ";" }
    let pipe_pair = pair.into_inner().next().unwrap();
    let expr = super::expressions::parse_pipe_chain(pipe_pair)?;
    Ok(Statement::ExprStatement {
        expr,
        span: None,
    })
}

fn parse_match_expr_stmt(pair: Pair<Rule>) -> Result<Statement, ParseError> {
    // match_expr_stmt = { match_expr }
    let match_pair = pair.into_inner().next().unwrap();
    let expr = super::expressions::parse_match(match_pair)?;
    Ok(Statement::ExprStatement {
        expr,
        span: None,
    })
}
