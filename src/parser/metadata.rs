use pest::iterators::Pair;

use crate::ast::common::{Metadata, MetaField, MetaValue};
use crate::ast::epistemic::{EpMode, Freshness, Scope, Src};
use crate::errors::ParseError;
use crate::grammar::Rule;

/// Parse a metadata block: | p:0.7 | ep:infer | src:obs(sensor) | scope:loc | t:fresh
pub fn parse_metadata(pair: Pair<Rule>) -> Result<Metadata, ParseError> {
    let mut meta = Metadata::default();

    for field_pair in pair.into_inner() {
        if field_pair.as_rule() != Rule::meta_field {
            continue;
        }
        let span = field_pair.as_span();
        let (line, col) = span.start_pos().line_col();
        let mut inner = field_pair.into_inner();

        let key_pair = inner.next().ok_or_else(|| ParseError::Syntax {
            line,
            col,
            message: "expected metadata key".to_string(),
        })?;
        let key = key_pair.as_str();

        let value_pair = inner.next().ok_or_else(|| ParseError::Syntax {
            line,
            col,
            message: format!("expected value for metadata key '{}'", key),
        })?;

        match key {
            "p" => {
                meta.confidence = Some(parse_float_value(value_pair, line, col)?);
            }
            "ep" => {
                meta.ep_mode = Some(parse_ep_mode(value_pair, line, col)?);
            }
            "src" => {
                meta.source = Some(parse_src(value_pair)?);
            }
            "scope" => {
                meta.scope = Some(parse_scope(value_pair, line, col)?);
            }
            "t" => {
                meta.freshness = Some(parse_freshness(value_pair, line, col)?);
            }
            other => {
                let value = parse_meta_value(value_pair)?;
                meta.extra.push(MetaField {
                    key: other.to_string(),
                    value,
                });
            }
        }
    }

    Ok(meta)
}

fn parse_float_value(pair: Pair<Rule>, line: usize, col: usize) -> Result<f64, ParseError> {
    pair.as_str().parse::<f64>().map_err(|_| ParseError::Syntax {
        line,
        col,
        message: format!("invalid confidence value: {}", pair.as_str()),
    })
}

fn parse_ep_mode(pair: Pair<Rule>, line: usize, col: usize) -> Result<EpMode, ParseError> {
    match pair.as_str() {
        "direct" => Ok(EpMode::Direct),
        "infer" => Ok(EpMode::Infer),
        "anl" => Ok(EpMode::Anl),
        "recv" => Ok(EpMode::Recv),
        other => Err(ParseError::Syntax {
            line,
            col,
            message: format!("unknown epistemic mode: {}", other),
        }),
    }
}

fn parse_scope(pair: Pair<Rule>, line: usize, col: usize) -> Result<Scope, ParseError> {
    match pair.as_str() {
        "all" => Ok(Scope::All),
        "some" => Ok(Scope::Some),
        "none" => Ok(Scope::None),
        "cond" => Ok(Scope::Cond),
        "gen" => Ok(Scope::Gen),
        "loc" => Ok(Scope::Loc),
        other => Err(ParseError::Syntax {
            line,
            col,
            message: format!("unknown scope: {}", other),
        }),
    }
}

fn parse_freshness(pair: Pair<Rule>, line: usize, col: usize) -> Result<Freshness, ParseError> {
    match pair.as_str() {
        "fresh" => Ok(Freshness::Fresh),
        "stale" => Ok(Freshness::Stale),
        "unk" => Ok(Freshness::Unk),
        other => Err(ParseError::Syntax {
            line,
            col,
            message: format!("unknown freshness: {}", other),
        }),
    }
}

fn parse_src(pair: Pair<Rule>) -> Result<Src, ParseError> {
    match pair.as_rule() {
        Rule::operator_call => {
            let mut inner = pair.into_inner();
            let name_pair = inner.next().unwrap();
            let name = name_pair.as_str();
            if name == "obs" {
                // obs(sensor) => Src::Obs("sensor")
                if let Some(arg_list) = inner.next() {
                    if let Some(arg) = arg_list.into_inner().next() {
                        // arg -> expr -> primary_expr or ident
                        let text = extract_ident_text(&arg);
                        return Ok(Src::Obs(text));
                    }
                }
                Ok(Src::Obs(String::new()))
            } else {
                Ok(Src::Obs(name.to_string()))
            }
        }
        Rule::ident => {
            let s = pair.as_str();
            match s {
                "Given" | "given" => Ok(Src::Given),
                other => Ok(Src::Obs(other.to_string())),
            }
        }
        _ => Ok(Src::Given),
    }
}

fn parse_meta_value(pair: Pair<Rule>) -> Result<MetaValue, ParseError> {
    match pair.as_rule() {
        Rule::float_literal => {
            let v = pair.as_str().parse::<f64>().unwrap_or(0.0);
            Ok(MetaValue::Float(v))
        }
        Rule::ident => Ok(MetaValue::Ident(pair.as_str().to_string())),
        Rule::string_literal => {
            let s = pair.as_str();
            // Strip quotes
            let inner = if s.starts_with('"') && s.ends_with('"') {
                &s[1..s.len() - 1]
            } else {
                s
            };
            Ok(MetaValue::Str(inner.to_string()))
        }
        Rule::operator_call => {
            let mut inner = pair.into_inner();
            let name = inner.next().unwrap().as_str().to_string();
            let args = if let Some(arg_list) = inner.next() {
                arg_list
                    .into_inner()
                    .map(|arg| {
                        // Each arg contains an expr
                        let expr_pair = arg.into_inner().next().unwrap();
                        super::expressions::parse_expr(expr_pair)
                    })
                    .collect::<Result<Vec<_>, _>>()?
            } else {
                vec![]
            };
            Ok(MetaValue::Call(name, args))
        }
        _ => Ok(MetaValue::Ident(pair.as_str().to_string())),
    }
}

/// Recursively extract identifier text from deeply nested pair structures
fn extract_ident_text(pair: &Pair<Rule>) -> String {
    match pair.as_rule() {
        Rule::ident => pair.as_str().to_string(),
        Rule::arg => {
            if let Some(inner) = pair.clone().into_inner().next() {
                extract_ident_text(&inner)
            } else {
                pair.as_str().to_string()
            }
        }
        Rule::expr | Rule::primary_expr => {
            if let Some(inner) = pair.clone().into_inner().next() {
                extract_ident_text(&inner)
            } else {
                pair.as_str().to_string()
            }
        }
        _ => pair.as_str().trim().to_string(),
    }
}
