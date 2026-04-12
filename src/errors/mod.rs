pub mod diagnostic;

#[derive(Debug, thiserror::Error)]
pub enum ParseError {
    #[error("parse error at {line}:{col}: {message}")]
    Syntax {
        line: usize,
        col: usize,
        message: String,
    },
    #[error("unexpected token: expected {expected}, found {found}")]
    UnexpectedToken {
        expected: String,
        found: String,
    },
}

#[derive(Debug, thiserror::Error)]
pub enum ValidationError {
    #[error("phase error: {message}")]
    Phase { message: String },
    #[error("metadata error: {message}")]
    Metadata { message: String },
    #[error("bounds error: {message}")]
    Bounds { message: String },
    #[error("resource error: {message}")]
    Resource { message: String },
    #[error("type error: {message}")]
    Type { message: String },
    #[error("semantic error: {message}")]
    Semantic { message: String },
}
