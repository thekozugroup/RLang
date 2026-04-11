use serde::{Deserialize, Serialize};

/// A2A-aligned task state
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub enum TaskState {
    Submitted,
    Working,
    InputRequired,
    AuthRequired,
    Completed,
    Failed,
    Canceled,
    Rejected,
}

impl TaskState {
    pub fn is_terminal(&self) -> bool {
        matches!(self, Self::Completed | Self::Failed | Self::Canceled | Self::Rejected)
    }

    pub fn valid_transitions(&self) -> Vec<TaskState> {
        match self {
            Self::Submitted     => vec![Self::Working, Self::Rejected, Self::Canceled],
            Self::Working       => vec![Self::Completed, Self::Failed, Self::Canceled, Self::InputRequired, Self::AuthRequired],
            Self::InputRequired => vec![Self::Working, Self::Canceled],
            Self::AuthRequired  => vec![Self::Working, Self::Canceled],
            Self::Completed | Self::Failed | Self::Canceled | Self::Rejected => vec![],
        }
    }
}

/// Contract mode for delegation
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum ContractMode {
    Urgent,
    Economical,
    Balanced,
}

/// Role in a message exchange
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum Role {
    User,
    Agent,
}
