use pest::iterators::Pair;

use crate::ast::common::*;
use crate::ast::connectives::Connective;
use crate::errors::ParseError;
use crate::grammar::Rule;

use super::metadata::parse_metadata;

/// Parse any expression (the top-level `expr` rule dispatches to sub-rules)
pub fn parse_expr(pair: Pair<Rule>) -> Result<Expr, ParseError> {
    let span = pair.as_span();
    let (line, col) = span.start_pos().line_col();

    match pair.as_rule() {
        Rule::expr => {
            // expr = { match_expr | pipe_chain | primary_expr }
            let inner = pair.into_inner().next().ok_or_else(|| ParseError::Syntax {
                line,
                col,
                message: "empty expression".to_string(),
            })?;
            parse_expr(inner)
        }
        Rule::primary_expr => {
            let inner = pair.into_inner().next().ok_or_else(|| ParseError::Syntax {
                line,
                col,
                message: "empty primary expression".to_string(),
            })?;
            parse_expr(inner)
        }
        Rule::operator_call => parse_operator_call(pair),
        Rule::result_expr => parse_result_expr(pair),
        Rule::evidence_block => parse_evidence_block(pair),
        Rule::array_literal => parse_array(pair),
        Rule::struct_literal => parse_struct(pair),
        Rule::match_expr => parse_match(pair),
        Rule::pipe_chain => parse_pipe_chain(pair),
        Rule::float_literal => {
            let v = pair.as_str().parse::<f64>().map_err(|_| ParseError::Syntax {
                line,
                col,
                message: format!("invalid float: {}", pair.as_str()),
            })?;
            Ok(Expr::Literal(Literal::Float(v)))
        }
        Rule::int_literal => {
            let v = pair.as_str().parse::<i64>().map_err(|_| ParseError::Syntax {
                line,
                col,
                message: format!("invalid integer: {}", pair.as_str()),
            })?;
            Ok(Expr::Literal(Literal::Int(v)))
        }
        Rule::string_literal => {
            let s = pair.as_str();
            let inner = if s.starts_with('"') && s.ends_with('"') {
                &s[1..s.len() - 1]
            } else {
                s
            };
            Ok(Expr::Literal(Literal::Str(inner.to_string())))
        }
        Rule::bool_literal => {
            let v = pair.as_str() == "true";
            Ok(Expr::Literal(Literal::Bool(v)))
        }
        Rule::literal => {
            let inner = pair.into_inner().next().ok_or_else(|| ParseError::Syntax {
                line,
                col,
                message: "empty literal".to_string(),
            })?;
            parse_expr(inner)
        }
        Rule::signed_number => {
            let v = pair.as_str().parse::<f64>().map_err(|_| ParseError::Syntax {
                line,
                col,
                message: format!("invalid signed number: {}", pair.as_str()),
            })?;
            Ok(Expr::Literal(Literal::Float(v)))
        }
        Rule::unit_literal => {
            // () represented as a special identifier
            Ok(Expr::Ident(Ident("()".to_string())))
        }
        Rule::ident => Ok(Expr::Ident(Ident(pair.as_str().to_string()))),
        Rule::arg => {
            // arg = { expr ~ metadata? }
            let mut inner = pair.into_inner();
            let expr = parse_expr(inner.next().unwrap())?;
            if let Some(meta_pair) = inner.next() {
                let metadata = parse_metadata(meta_pair)?;
                Ok(Expr::WithMetadata {
                    expr: Box::new(expr),
                    metadata,
                    span: None,
                })
            } else {
                Ok(expr)
            }
        }
        _ => Err(ParseError::Syntax {
            line,
            col,
            message: format!("unexpected rule in expression: {:?}", pair.as_rule()),
        }),
    }
}

/// Known operator names -> Operator enum variant
fn lookup_operator(name: &str) -> Option<Operator> {
    match name {
        // Layer 1: Epistemic core
        "cause" => Some(Operator::Cause),
        "prvnt" => Some(Operator::Prvnt),
        "enbl" => Some(Operator::Enbl),
        "req" => Some(Operator::Req),
        "obs" => Some(Operator::Obs),
        "sim" => Some(Operator::Sim),
        "confl" => Some(Operator::Confl),
        "chng" => Some(Operator::Chng),
        "cncl" => Some(Operator::Cncl),
        "cntns" => Some(Operator::Cntns),
        "isa" => Some(Operator::Isa),
        "seq" => Some(Operator::Seq),
        "goal" => Some(Operator::Goal),
        // Layer 1: Evidence modifiers
        "sup" => Some(Operator::Sup),
        "wkn" => Some(Operator::Wkn),
        "neut" => Some(Operator::Neut),
        // Layer 1: Resolution
        "resolve" => Some(Operator::Resolve),
        "conf" => Some(Operator::Conf),
        "decay" => Some(Operator::Decay),
        "refresh" => Some(Operator::Refresh),
        // Layer 2: Motivational
        "dcmp" => Some(Operator::Dcmp),
        "prioritize" => Some(Operator::Prioritize),
        "select" => Some(Operator::Select),
        "replan" => Some(Operator::Replan),
        // Layer 3: Operational
        "exec" => Some(Operator::Exec),
        "inv" => Some(Operator::Inv),
        "pcv" => Some(Operator::Pcv),
        "rmb" => Some(Operator::Rmb),
        "rcl" => Some(Operator::Rcl),
        "forget" => Some(Operator::Forget),
        "bt" => Some(Operator::Bt),
        "verify" => Some(Operator::Verify),
        "retry_with" => Some(Operator::RetryWith),
        // Layer 4: Communicative
        "dlg" => Some(Operator::Dlg),
        "msg" => Some(Operator::Msg),
        "discover" => Some(Operator::Discover),
        "match_capability" => Some(Operator::MatchCapability),
        "negotiate" => Some(Operator::Negotiate),
        "cancel" => Some(Operator::Cancel),
        "poll" => Some(Operator::Poll),
        "subscribe" => Some(Operator::Subscribe),
        "cfp" => Some(Operator::Cfp),
        "propose" => Some(Operator::Propose),
        "accept_proposal" => Some(Operator::AcceptProposal),
        "reject_proposal" => Some(Operator::RejectProposal),
        "inform" => Some(Operator::Inform),
        "query_if" => Some(Operator::QueryIf),
        "agree" => Some(Operator::Agree),
        "refuse" => Some(Operator::Refuse),
        "resolve_conflict" => Some(Operator::ResolveConflict),
        // Assertion-like
        "assert" => Some(Operator::Assert),
        "hedge" => Some(Operator::Hedge),
        "suspend" => Some(Operator::Suspend),
        "reject" => Some(Operator::Reject),
        "emit" => Some(Operator::Emit),
        _ => None,
    }
}

fn parse_operator_call(pair: Pair<Rule>) -> Result<Expr, ParseError> {
    let mut inner = pair.into_inner();

    // operator_name -> ident
    let name_pair = inner.next().unwrap();
    let name_str = name_pair.into_inner().next().unwrap().as_str();

    // arg_list -> arg*
    let args = if let Some(arg_list_pair) = inner.next() {
        parse_arg_list(arg_list_pair)?
    } else {
        vec![]
    };

    // Check if this is actually a Result variant (Ok, Err, Some, None)
    // The grammar matches these as operator_call because operator_name = { ident }
    // and Ok/Err/Some/None are valid idents.
    match name_str {
        "Ok" => {
            return Ok(Expr::ResultExpr {
                variant: ResultVariant::Ok,
                inner: args.into_iter().next().map(Box::new),
                span: None,
            });
        }
        "Err" => {
            return Ok(Expr::ResultExpr {
                variant: ResultVariant::Err,
                inner: args.into_iter().next().map(Box::new),
                span: None,
            });
        }
        "Some" => {
            return Ok(Expr::ResultExpr {
                variant: ResultVariant::Some,
                inner: args.into_iter().next().map(Box::new),
                span: None,
            });
        }
        "None" => {
            return Ok(Expr::ResultExpr {
                variant: ResultVariant::None,
                inner: None,
                span: None,
            });
        }
        _ => {}
    }

    if let Some(op) = lookup_operator(name_str) {
        Ok(Expr::OperatorCall {
            name: op,
            args,
            span: None,
        })
    } else {
        Ok(Expr::FnCall {
            name: Ident(name_str.to_string()),
            args,
            span: None,
        })
    }
}

fn parse_arg_list(pair: Pair<Rule>) -> Result<Vec<Expr>, ParseError> {
    pair.into_inner()
        .map(|arg_pair| parse_expr(arg_pair))
        .collect()
}

fn parse_result_expr(pair: Pair<Rule>) -> Result<Expr, ParseError> {
    let mut inner = pair.into_inner();
    let variant_pair = inner.next().unwrap();
    let variant = match variant_pair.as_str() {
        "Ok" => ResultVariant::Ok,
        "Err" => ResultVariant::Err,
        "Some" => ResultVariant::Some,
        "None" => ResultVariant::None,
        other => {
            let (line, col) = variant_pair.as_span().start_pos().line_col();
            return Err(ParseError::Syntax {
                line,
                col,
                message: format!("unknown result variant: {}", other),
            });
        }
    };

    let inner_expr = if let Some(expr_pair) = inner.next() {
        Some(Box::new(parse_expr(expr_pair)?))
    } else {
        None
    };

    Ok(Expr::ResultExpr {
        variant,
        inner: inner_expr,
        span: None,
    })
}

fn parse_evidence_block(pair: Pair<Rule>) -> Result<Expr, ParseError> {
    let mut items = Vec::new();
    for item_pair in pair.into_inner() {
        if item_pair.as_rule() == Rule::evidence_item {
            let mut inner = item_pair.into_inner();
            let obs = parse_expr(inner.next().unwrap())?;
            let effect = parse_expr(inner.next().unwrap())?;
            items.push(EvidenceItem {
                observation: obs,
                effect,
            });
        }
    }
    Ok(Expr::EvidenceBlock {
        items,
        span: None,
    })
}

fn parse_array(pair: Pair<Rule>) -> Result<Expr, ParseError> {
    let elements: Result<Vec<_>, _> = pair
        .into_inner()
        .filter(|p| p.as_rule() == Rule::array_item)
        .map(|item| {
            let inner = item.into_inner().next().unwrap();
            parse_expr(inner)
        })
        .collect();
    Ok(Expr::Array {
        elements: elements?,
        span: None,
    })
}

fn parse_struct(pair: Pair<Rule>) -> Result<Expr, ParseError> {
    let mut inner = pair.into_inner();
    let name = Ident(inner.next().unwrap().as_str().to_string());
    let mut fields = Vec::new();
    for field_pair in inner {
        if field_pair.as_rule() == Rule::struct_field {
            let mut field_inner = field_pair.into_inner();
            let key = Ident(field_inner.next().unwrap().as_str().to_string());
            let value = parse_expr(field_inner.next().unwrap())?;
            fields.push((key, value));
        }
    }
    Ok(Expr::Struct {
        name,
        fields,
        span: None,
    })
}

pub fn parse_match(pair: Pair<Rule>) -> Result<Expr, ParseError> {
    let mut inner = pair.into_inner();
    let scrutinee = parse_expr(inner.next().unwrap())?;
    let mut arms = Vec::new();

    for arm_pair in inner {
        if arm_pair.as_rule() == Rule::match_arm {
            let mut arm_inner = arm_pair.into_inner();
            let pattern = parse_pattern(arm_inner.next().unwrap())?;
            let body = parse_expr(arm_inner.next().unwrap())?;
            arms.push(MatchArm {
                pattern,
                body,
                span: None,
            });
        }
    }

    Ok(Expr::Match {
        scrutinee: Box::new(scrutinee),
        arms,
        span: None,
    })
}

fn parse_pattern(pair: Pair<Rule>) -> Result<Pattern, ParseError> {
    let inner = pair.into_inner().next().unwrap();
    match inner.as_rule() {
        Rule::wildcard => Ok(Pattern::Wildcard),
        Rule::guard_pattern => {
            let mut gp_inner = inner.into_inner();
            let binding = Ident(gp_inner.next().unwrap().as_str().to_string());
            // guard_condition: ident ~ comparison_op ~ primary_expr
            let cond_pair = gp_inner.next().unwrap();
            let mut cond_inner = cond_pair.into_inner();
            let left = Ident(cond_inner.next().unwrap().as_str().to_string());
            let op_pair = cond_inner.next().unwrap();
            let op = parse_comparison_op(op_pair)?;
            let right = parse_expr(cond_inner.next().unwrap())?;
            Ok(Pattern::Guard {
                binding,
                condition: GuardCondition { left, op, right },
            })
        }
        Rule::literal => {
            let lit_inner = inner.into_inner().next().unwrap();
            match lit_inner.as_rule() {
                Rule::float_literal => Ok(Pattern::Literal(Literal::Float(
                    lit_inner.as_str().parse().unwrap_or(0.0),
                ))),
                Rule::int_literal => Ok(Pattern::Literal(Literal::Int(
                    lit_inner.as_str().parse().unwrap_or(0),
                ))),
                Rule::string_literal => {
                    let s = lit_inner.as_str();
                    let inner_s = if s.starts_with('"') && s.ends_with('"') {
                        &s[1..s.len() - 1]
                    } else {
                        s
                    };
                    Ok(Pattern::Literal(Literal::Str(inner_s.to_string())))
                }
                Rule::bool_literal => {
                    Ok(Pattern::Literal(Literal::Bool(lit_inner.as_str() == "true")))
                }
                _ => Ok(Pattern::Ident(Ident(lit_inner.as_str().to_string()))),
            }
        }
        Rule::ident => Ok(Pattern::Ident(Ident(inner.as_str().to_string()))),
        _ => {
            let (line, col) = inner.as_span().start_pos().line_col();
            Err(ParseError::Syntax {
                line,
                col,
                message: format!("unexpected pattern rule: {:?}", inner.as_rule()),
            })
        }
    }
}

fn parse_comparison_op(pair: Pair<Rule>) -> Result<ComparisonOp, ParseError> {
    match pair.as_str() {
        ">" => Ok(ComparisonOp::Gt),
        "<" => Ok(ComparisonOp::Lt),
        ">=" => Ok(ComparisonOp::Gte),
        "<=" => Ok(ComparisonOp::Lte),
        "==" => Ok(ComparisonOp::Eq),
        "!=" => Ok(ComparisonOp::Neq),
        other => {
            let (line, col) = pair.as_span().start_pos().line_col();
            Err(ParseError::Syntax {
                line,
                col,
                message: format!("unknown comparison operator: {}", other),
            })
        }
    }
}

pub fn parse_pipe_chain(pair: Pair<Rule>) -> Result<Expr, ParseError> {
    let mut inner = pair.into_inner();
    let first = parse_expr(inner.next().unwrap())?;
    let mut steps = vec![];

    while let Some(conn_pair) = inner.next() {
        if conn_pair.as_rule() != Rule::connective {
            // Could be a primary_expr if pipe_chain allows optional RHS
            continue;
        }
        let connective = parse_connective(&conn_pair)?;

        // RHS is optional in the grammar: primary_expr?
        if let Some(next_pair) = inner.peek() {
            if next_pair.as_rule() != Rule::connective {
                let expr_pair = inner.next().unwrap();
                steps.push((connective, parse_expr(expr_pair)?));
            } else {
                // No RHS before next connective — use unit
                steps.push((connective, Expr::Ident(Ident("()".to_string()))));
            }
        } else {
            // No more tokens — connective without RHS (e.g., <@ at end)
            steps.push((connective, Expr::Ident(Ident("()".to_string()))));
        }
    }

    if steps.is_empty() {
        Ok(first)
    } else {
        // Build the chain: first element gets Pipe as a dummy connective
        Ok(Expr::PipeChain {
            steps: std::iter::once((Connective::Pipe, first))
                .chain(steps)
                .collect(),
            span: None,
        })
    }
}

fn parse_connective(pair: &Pair<Rule>) -> Result<Connective, ParseError> {
    match pair.as_str() {
        "|>" => Ok(Connective::Pipe),
        "->" => Ok(Connective::Transform),
        "||>" => Ok(Connective::FanOut),
        "<|" => Ok(Connective::Aggregate),
        "~>" => Ok(Connective::Tentative),
        "!>" => Ok(Connective::ErrChannel),
        "?>" => Ok(Connective::Fallible),
        "@>" => Ok(Connective::Store),
        "<@" => Ok(Connective::Retrieve),
        other => {
            let (line, col) = pair.as_span().start_pos().line_col();
            Err(ParseError::Syntax {
                line,
                col,
                message: format!("unknown connective: {}", other),
            })
        }
    }
}
