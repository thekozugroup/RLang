use serde::{Deserialize, Serialize};

/// All connective operators in RLang
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum Connective {
    Pipe,       // |>  — sequential pipe
    Transform,  // ->  — transform/resolve
    FanOut,     // ||> — parallel fan-out
    Aggregate,  // <|  — merge multiple into one
    Tentative,  // ~>  — exploratory (revertible)
    ErrChannel, // !>  — error routing
    Fallible,   // ?>  — try left, on fail try right
    Store,      // @>  — pipe to memory
    Retrieve,   // <@  — pull from memory
}
