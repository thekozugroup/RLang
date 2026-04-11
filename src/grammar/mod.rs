use pest_derive::Parser;

#[derive(Parser)]
#[grammar = "grammar/rlang.pest"]
pub struct RLangParser;
