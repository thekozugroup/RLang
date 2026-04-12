use serde::{Deserialize, Serialize};

use super::templates::TrainingExample;

/// JSONL export format — one JSON object per line
#[derive(Debug, Serialize, Deserialize)]
pub struct JsonlEntry {
    pub prompt: String,
    pub rlang_trace: String,
    pub conclusion: String,
    pub domain: String,
    pub difficulty: String,
}

/// ShareGPT export format — messages array with roles
#[derive(Debug, Serialize, Deserialize)]
pub struct ShareGptConversation {
    pub conversations: Vec<ShareGptMessage>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct ShareGptMessage {
    pub from: String,
    pub value: String,
}

/// Export examples to JSONL format (one JSON per line)
pub fn to_jsonl(examples: &[TrainingExample]) -> String {
    examples
        .iter()
        .map(|ex| {
            let entry = JsonlEntry {
                prompt: ex.prompt.clone(),
                rlang_trace: ex.rlang_trace.clone(),
                conclusion: ex.conclusion.clone(),
                domain: ex.domain.clone(),
                difficulty: ex.difficulty.clone(),
            };
            serde_json::to_string(&entry).expect("failed to serialize JSONL entry")
        })
        .collect::<Vec<_>>()
        .join("\n")
}

/// Export examples to ShareGPT format with <think> tags around RLang trace
/// (matching DeepSeek R1 convention)
pub fn to_sharegpt(examples: &[TrainingExample]) -> String {
    let conversations: Vec<ShareGptConversation> = examples
        .iter()
        .map(|ex| {
            let system_msg = ShareGptMessage {
                from: "system".to_string(),
                value: "You are a structured reasoning agent. When solving problems, \
                        think through them using RLang reasoning traces, then provide \
                        a clear conclusion."
                    .to_string(),
            };

            let user_msg = ShareGptMessage {
                from: "human".to_string(),
                value: ex.prompt.clone(),
            };

            let assistant_value = format!(
                "<think>\n{}\n</think>\n\n{}",
                ex.rlang_trace, ex.conclusion
            );
            let assistant_msg = ShareGptMessage {
                from: "gpt".to_string(),
                value: assistant_value,
            };

            ShareGptConversation {
                conversations: vec![system_msg, user_msg, assistant_msg],
            }
        })
        .collect();

    serde_json::to_string_pretty(&conversations).expect("failed to serialize ShareGPT")
}

/// Export a single example to JSONL entry string
pub fn example_to_jsonl(example: &TrainingExample) -> String {
    let entry = JsonlEntry {
        prompt: example.prompt.clone(),
        rlang_trace: example.rlang_trace.clone(),
        conclusion: example.conclusion.clone(),
        domain: example.domain.clone(),
        difficulty: example.difficulty.clone(),
    };
    serde_json::to_string(&entry).expect("failed to serialize JSONL entry")
}
