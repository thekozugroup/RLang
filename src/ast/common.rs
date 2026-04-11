use serde::{Deserialize, Serialize};

/// Source span for error reporting
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Span {
    pub start: usize,
    pub end: usize,
    pub line: usize,
    pub col: usize,
}

/// Any identifier in the language
#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct Ident(pub String);

/// Numeric literal
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum Literal {
    Float(f64),
    Int(i64),
    Str(String),
    Bool(bool),
}
