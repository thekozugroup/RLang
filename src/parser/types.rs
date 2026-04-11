use pest::iterators::Pair;

use crate::ast::common::{TypeAnnotation, TypeParam};
use crate::errors::ParseError;
use crate::grammar::Rule;

/// Parse a type annotation: blf<0.7, 'fresh>, goal<Deploy>, etc.
pub fn parse_type_annotation(pair: Pair<Rule>) -> Result<TypeAnnotation, ParseError> {
    let inner = pair.into_inner().next().unwrap();
    match inner.as_rule() {
        Rule::generic_type => parse_generic_type(inner),
        Rule::simple_type => {
            Ok(TypeAnnotation::Simple(inner.as_str().to_string()))
        }
        _ => {
            let (line, col) = inner.as_span().start_pos().line_col();
            Err(ParseError::Syntax {
                line,
                col,
                message: format!("unexpected type annotation rule: {:?}", inner.as_rule()),
            })
        }
    }
}

fn parse_generic_type(pair: Pair<Rule>) -> Result<TypeAnnotation, ParseError> {
    let mut inner = pair.into_inner();

    // simple_type (base)
    let base = inner.next().unwrap().as_str().to_string();

    // type_params
    let params = if let Some(params_pair) = inner.next() {
        parse_type_params(params_pair)?
    } else {
        vec![]
    };

    Ok(TypeAnnotation::Generic { base, params })
}

fn parse_type_params(pair: Pair<Rule>) -> Result<Vec<TypeParam>, ParseError> {
    pair.into_inner()
        .map(|param_pair| parse_type_param(param_pair))
        .collect()
}

fn parse_type_param(pair: Pair<Rule>) -> Result<TypeParam, ParseError> {
    let inner = pair.into_inner().next().unwrap();
    match inner.as_rule() {
        Rule::float_literal => {
            let v = inner.as_str().parse::<f64>().unwrap_or(0.0);
            Ok(TypeParam::Float(v))
        }
        Rule::lifetime => {
            // lifetime = { "'" ~ ident }
            let ident = inner.into_inner().next().unwrap().as_str();
            Ok(TypeParam::Lifetime(ident.to_string()))
        }
        Rule::type_annotation => {
            let ta = parse_type_annotation(inner)?;
            Ok(TypeParam::Type(Box::new(ta)))
        }
        Rule::ident => Ok(TypeParam::Ident(inner.as_str().to_string())),
        _ => {
            let (line, col) = inner.as_span().start_pos().line_col();
            Err(ParseError::Syntax {
                line,
                col,
                message: format!("unexpected type param rule: {:?}", inner.as_rule()),
            })
        }
    }
}
