use super::{ParseError, ValidationError};

/// Rust-style diagnostic formatter for RLang errors.
///
/// Produces output like:
/// ```text
/// error[E0001]: unexpected token
///  --> examples/deploy.rl:3:12
///   |
/// 3 |     let x = bad syntax;
///   |            ^
/// ```
pub struct Diagnostic<'a> {
    pub source: &'a str,
    pub filename: &'a str,
}

impl<'a> Diagnostic<'a> {
    pub fn new(source: &'a str, filename: &'a str) -> Self {
        Self { source, filename }
    }

    /// Format a parse error with source location and caret pointer.
    pub fn format_parse_error(&self, err: &ParseError) -> String {
        match err {
            ParseError::Syntax { line, col, message } => {
                let line_content = self.source.lines().nth(line.saturating_sub(1)).unwrap_or("");
                let line_num_width = line.to_string().len();
                let padding = " ".repeat(line_num_width);
                let caret_padding = " ".repeat(col.saturating_sub(1));
                format!(
                    "\x1b[1;31merror[E0001]\x1b[0m\x1b[1m: parse error\x1b[0m\n \
                     \x1b[1;34m-->\x1b[0m {}:{}:{}\n \
                     {}\x1b[1;34m|\x1b[0m\n\
\x1b[1;34m{}\x1b[0m \x1b[1;34m|\x1b[0m {}\n \
                     {}\x1b[1;34m|\x1b[0m {}\x1b[1;31m^\x1b[0m\n \
                     {}\x1b[1;34m|\x1b[0m\n \
                     {}\x1b[1;34m= note:\x1b[0m {}",
                    self.filename,
                    line,
                    col,
                    padding,
                    line,
                    line_content,
                    padding,
                    caret_padding,
                    padding,
                    padding,
                    message,
                )
            }
            ParseError::UnexpectedToken { expected, found } => {
                format!(
                    "\x1b[1;31merror[E0002]\x1b[0m\x1b[1m: unexpected token\x1b[0m\n \
                     \x1b[1;34m-->\x1b[0m {}\n \
                     \x1b[1;34m= note:\x1b[0m expected {}, found {}",
                    self.filename, expected, found,
                )
            }
        }
    }

    /// Format a validation error with error code and location.
    pub fn format_validation_error(&self, err: &ValidationError) -> String {
        let (code, category, message) = match err {
            ValidationError::Phase { message } => ("V0001", "phase order", message.as_str()),
            ValidationError::Metadata { message } => ("V0002", "metadata", message.as_str()),
            ValidationError::Bounds { message } => ("V0003", "bounds", message.as_str()),
            ValidationError::Resource { message } => ("V0004", "resource", message.as_str()),
            ValidationError::Type { message } => ("V0005", "type", message.as_str()),
            ValidationError::Semantic { message } => ("V0006", "semantic", message.as_str()),
        };

        format!(
            "\x1b[1;31merror[{}]\x1b[0m\x1b[1m: {} violation\x1b[0m\n \
             \x1b[1;34m-->\x1b[0m {}\n \
             \x1b[1;34m= note:\x1b[0m {}",
            code, category, self.filename, message,
        )
    }

    /// Format a parse error without ANSI color codes (for testing or piped output).
    pub fn format_parse_error_plain(&self, err: &ParseError) -> String {
        match err {
            ParseError::Syntax { line, col, message } => {
                let line_content = self.source.lines().nth(line.saturating_sub(1)).unwrap_or("");
                let line_num_width = line.to_string().len();
                let padding = " ".repeat(line_num_width);
                let caret_padding = " ".repeat(col.saturating_sub(1));
                format!(
                    "error[E0001]: parse error\n \
                     --> {}:{}:{}\n \
                     {}|\n\
{} | {}\n \
                     {}| {}^\n \
                     {}|\n \
                     {}= note: {}",
                    self.filename,
                    line,
                    col,
                    padding,
                    line,
                    line_content,
                    padding,
                    caret_padding,
                    padding,
                    padding,
                    message,
                )
            }
            ParseError::UnexpectedToken { expected, found } => {
                format!(
                    "error[E0002]: unexpected token\n \
                     --> {}\n \
                     = note: expected {}, found {}",
                    self.filename, expected, found,
                )
            }
        }
    }

    /// Format a validation error without ANSI color codes.
    pub fn format_validation_error_plain(&self, err: &ValidationError) -> String {
        let (code, category, message) = match err {
            ValidationError::Phase { message } => ("V0001", "phase order", message.as_str()),
            ValidationError::Metadata { message } => ("V0002", "metadata", message.as_str()),
            ValidationError::Bounds { message } => ("V0003", "bounds", message.as_str()),
            ValidationError::Resource { message } => ("V0004", "resource", message.as_str()),
            ValidationError::Type { message } => ("V0005", "type", message.as_str()),
            ValidationError::Semantic { message } => ("V0006", "semantic", message.as_str()),
        };

        format!(
            "error[{}]: {} violation\n \
             --> {}\n \
             = note: {}",
            code, category, self.filename, message,
        )
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_syntax_error_formatting() {
        let source = "let x = bad syntax;\nlet y = 42;";
        let diag = Diagnostic::new(source, "test.rl");
        let err = ParseError::Syntax {
            line: 1,
            col: 9,
            message: "expected expression".to_string(),
        };
        let output = diag.format_parse_error_plain(&err);
        assert!(output.contains("error[E0001]"));
        assert!(output.contains("test.rl:1:9"));
        assert!(output.contains("let x = bad syntax;"));
        assert!(output.contains("^"));
    }

    #[test]
    fn test_validation_error_formatting() {
        let diag = Diagnostic::new("", "test.rl");
        let err = ValidationError::Phase {
            message: "missing required Verify phase".to_string(),
        };
        let output = diag.format_validation_error_plain(&err);
        assert!(output.contains("error[V0001]"));
        assert!(output.contains("phase order violation"));
        assert!(output.contains("missing required Verify phase"));
    }

    #[test]
    fn test_unexpected_token_formatting() {
        let diag = Diagnostic::new("", "test.rl");
        let err = ParseError::UnexpectedToken {
            expected: "identifier".to_string(),
            found: "number".to_string(),
        };
        let output = diag.format_parse_error_plain(&err);
        assert!(output.contains("error[E0002]"));
        assert!(output.contains("expected identifier, found number"));
    }
}
