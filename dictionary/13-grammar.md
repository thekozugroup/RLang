# Formal Grammar Reference

[Back to Dictionary Index](./README.md) | [Previous: A2A Mapping](./12-a2a-mapping.md) | [Next: Examples](./14-examples.md)

---

## Overview

RLang uses a PEG (Parsing Expression Grammar) implemented with the Pest parser generator for Rust. The grammar defines the complete syntax of the language and enforces phase ordering at the structural level.

---

## Top-Level Structure

### trace

The top-level rule. A trace is one or more phase blocks.

```
trace = { SOI ~ phase_block+ ~ EOI }
```

**Description:** A complete reasoning trace must start at the beginning of input (`SOI`), contain one or more phase blocks, and end at the end of input (`EOI`). This ensures the entire input is consumed.

**Railroad diagram (text):**
```
[SOI] --> ( phase_block )+ --> [EOI]
```

---

## Phase Structure

### phase_block

A phase block is a phase attribute followed by either an impl block (with reasoning mode) or a bare block.

```
phase_block = { phase_attr ~ (impl_block | bare_block) }
```

**Description:** Each phase block begins with a `#[phase(Name)]` attribute, then contains either:
- An `impl` block declaring a reasoning mode: `impl Deductive { ... }`
- A bare block: `{ ... }`

### phase_attr

```
phase_attr = { "#[phase(" ~ phase_name ~ ")]" }
```

### phase_name

```
phase_name = { "Frame" | "Explore" | "Verify" | "Decide" }
```

**Description:** Exactly four valid phase names. The parser accepts them in any order at the grammar level; the validator enforces correct ordering.

### impl_block / bare_block

```
impl_block = { "impl" ~ reasoning_mode ~ "{" ~ statement* ~ "}" }
bare_block = { "{" ~ statement* ~ "}" }
```

### reasoning_mode

```
reasoning_mode = { "Deductive" | "Abductive" | "Analogical" }
```

**Phase ordering enforcement:** The grammar accepts phases in any order. The validator checks that phases appear in the correct sequence: Frame (0) < Explore (1) < Verify (2) < Decide (3), with bounded rebloom allowed from Verify back to Explore.

---

## Statements

### statement

```
statement = { let_binding | match_expr_stmt | pipe_chain_stmt | assertion }
```

**Description:** Four types of statements can appear inside phase blocks.

### let_binding

```
let_binding = {
    "let" ~ ident ~ (":" ~ type_annotation)? ~ "=" ~ expr ~ metadata? ~ ";"
}
```

**Railroad diagram (text):**
```
"let" --> ident --> [ ":" type_annotation ]? --> "=" --> expr --> [ metadata ]? --> ";"
```

**Description:** Variable binding with optional type annotation and metadata. The type annotation follows Rust syntax. Metadata is attached via `|` separators.

### assertion

```
assertion = {
    assertion_kw ~ "(" ~ arg_list ~ ")" ~ metadata? ~ ";"
}
assertion_kw = { "assert" | "hedge" | "suspend" | "reject" | "emit" }
```

**Description:** Terminal assertions used primarily in the Decide phase. The validator enforces that match arms in Decide use these keywords.

### pipe_chain_stmt

```
pipe_chain_stmt = { pipe_chain ~ ";" }
```

### match_expr_stmt

```
match_expr_stmt = { match_expr }
```

**Note:** Match expressions do not require a trailing semicolon because they are block-delimited by `{ }`.

---

## Expressions

### expr

```
expr = { match_expr | pipe_chain | primary_expr }
```

**Description:** Expressions are tried in order: match first, then pipe chain, then primary. This ordering ensures complex expressions are matched before simpler ones.

### primary_expr

```
primary_expr = {
    operator_call
    | result_expr
    | evidence_block
    | array_literal
    | struct_literal
    | unit_literal
    | signed_number
    | literal
    | "(" ~ expr ~ ")"
    | ident
}
```

**Description:** Primary expressions are the atomic building blocks. Tried in priority order:
1. Operator calls: `cause(a, b)`, `obs(x)`
2. Result expressions: `Ok(value)`, `Err(reason)`
3. Evidence blocks: `[obs => sup(...)]`
4. Array literals: `[a, b, c]`
5. Struct literals: `Name { field: value }`
6. Unit literal: `()`
7. Signed numbers: `+0.15`, `-0.25` (for evidence deltas)
8. Other literals: floats, ints, strings, bools
9. Parenthesized expressions: `(expr)`
10. Identifiers: variable references

### unit_literal

```
unit_literal = { "(" ~ ")" }
```

**Description:** The unit type `()`, used for void returns like `verify(x) -> Ok(())`.

### signed_number

```
signed_number = @{ ("+" | "-") ~ ASCII_DIGIT+ ~ "." ~ ASCII_DIGIT+ }
```

**Description:** Atomic rule for signed floating-point numbers used in evidence deltas: `+0.15`, `-0.25`. The `@` prefix makes this an atomic rule (no whitespace skipping inside).

---

## Operator Calls

### operator_call

```
operator_call = { operator_name ~ "(" ~ arg_list ~ ")" }
```

### operator_name

```
operator_name = { ident }
```

**Description:** At the grammar level, operator names are just identifiers. Keyword recognition (mapping identifiers like "cause", "obs", "sup" to the `Operator` enum) happens in the parser/AST layer. This avoids prefix-match issues (e.g., "exec" matching inside "execute").

### arg_list / arg

```
arg_list = { (arg ~ ("," ~ arg)*)? }
arg      = { expr ~ metadata? }
```

**Description:** Arguments are comma-separated expressions, each optionally followed by metadata.

---

## Pipe Chains and Connectives

### pipe_chain

```
pipe_chain = { primary_expr ~ (connective ~ primary_expr?)+ }
```

**Description:** A pipe chain starts with a primary expression followed by one or more connective-expression pairs. The `primary_expr?` is optional for connectives like `<@` that may not need a right-hand operand.

### connective

```
connective = {
    "||>"   // fan-out (must be before |>)
    | "|>"  // sequential pipe
    | "<|"  // aggregate
    | "<@"  // memory retrieve
    | "~>"  // tentative
    | "!>"  // error channel
    | "?>"  // fallible
    | "@>"  // memory store
    | "->"  // transform
}
```

**Description:** Nine connective operators. Ordering matters for PEG disambiguation:
- `||>` must come before `|>` to prevent the parser from matching `|` as a metadata separator followed by `|>`
- `<@` must come before `<|` in some contexts
- `->` is last as it is the most general

---

## Match Expressions

### match_expr

```
match_expr = { "match" ~ primary_expr ~ "{" ~ match_arm+ ~ "}" }
```

### match_arm

```
match_arm = { pattern ~ "=>" ~ expr ~ ","? }
```

### pattern

```
pattern = { wildcard | guard_pattern | literal | ident }
```

### guard_pattern

```
guard_pattern   = { ident ~ "if" ~ guard_condition }
guard_condition = { ident ~ comparison_op ~ primary_expr }
comparison_op   = { ">=" | "<=" | "!=" | ">" | "<" | "==" }
```

**Description:** Guard patterns allow conditional matching: `c if c > 0.85 => assert(claim)`. Multi-character operators (`>=`, `<=`, `!=`) are tried before single-character ones (`>`, `<`).

---

## Evidence Blocks

```
evidence_block = { "[" ~ evidence_item ~ ("," ~ evidence_item)* ~ ","? ~ "]" }
evidence_item  = { expr ~ "=>" ~ expr }
```

**Description:** Evidence blocks are array-like structures where each item maps an observation (left of `=>`) to an evidence effect (right of `=>`). The effect must use `sup()`, `wkn()`, or `neut()` (enforced by the validator, not the grammar).

---

## Metadata

```
metadata   = { ("|" ~ meta_field)+ }
meta_field = { meta_key ~ ":" ~ meta_value }
meta_key   = {
    "p" | "ep" | "src" | "scope" | "t"
    | "priority" | "deadline" | "success" | "mode"
    | "req" | "cond"
}
meta_value = { operator_call | float_literal | ident | string_literal }
```

**Description:** Metadata is attached via `|` separators. The `|` in metadata is always followed by a `meta_key` (identifier + colon), which disambiguates it from the `|>` pipe connective.

**Disambiguation:** `|` followed by a known meta_key and `:` is metadata. `|>` is a pipe connective.

---

## Type Annotations

```
type_annotation = { generic_type | simple_type }
generic_type    = { simple_type ~ "<" ~ type_params ~ ">" }
type_params     = { type_param ~ ("," ~ type_param)* }
type_param      = { float_literal | lifetime | type_annotation | ident }

simple_type = {
    "blf" | "goal" | "intent" | "action" | "obs_feed" | "reflection"
    | "Contract" | "Evidence" | "Plan" | "Task"
    | "CommAct" | "AgentCard" | "TrustModel"
    | "Result" | "Option" | "Vec" | "HashMap"
    | ident
}

lifetime = { "'" ~ ident }
```

**Description:** Type annotations follow Rust syntax. Generic types use angle brackets. Lifetimes use the `'name` syntax for freshness tracking.

---

## Struct and Array Literals

```
struct_literal = { ident ~ "{" ~ struct_field ~ ("," ~ struct_field)* ~ ","? ~ "}" }
struct_field   = { ident ~ ":" ~ expr }

array_literal = { "[" ~ (array_item ~ ("," ~ array_item)* ~ ","?)? ~ "]" }
array_item    = { expr }
```

---

## Result Expressions

```
result_expr    = { result_variant ~ "(" ~ expr ~ ")" }
result_variant = { "Ok" | "Err" | "Some" | "None" }
```

---

## Literals and Identifiers

```
literal        = { float_literal | int_literal | string_literal | bool_literal }
float_literal  = @{ ASCII_DIGIT+ ~ "." ~ ASCII_DIGIT+ }
int_literal    = @{ ASCII_DIGIT+ }
string_literal = @{ "\"" ~ (!"\"" ~ ANY)* ~ "\"" }
bool_literal   = { "true" | "false" }

ident = @{ (ASCII_ALPHA | "_") ~ (ASCII_ALPHANUMERIC | "_")* }
```

**Description:** Atomic rules (prefixed with `@`) do not skip whitespace internally. Identifiers start with a letter or underscore and contain alphanumeric characters and underscores.

---

## Whitespace and Comments

```
WHITESPACE = _{ " " | "\t" | "\r" | "\n" }
COMMENT    = _{ "//" ~ (!NEWLINE ~ ANY)* }
NEWLINE    = _{ "\n" | "\r\n" }
```

**Description:** Pest handles whitespace and comments automatically (silent rules prefixed with `_`). Line comments start with `//` and extend to end of line. These are automatically skipped between tokens.

---

## Bounded Attribute

```
bounded_attr   = { "#[bounded(" ~ bounded_params ~ ")]" }
bounded_params = { ident ~ (":" ~ literal)? ~ ("," ~ ident ~ (":" ~ literal)?)* }
```

**Description:** The `#[bounded]` attribute is used to limit iterations, retries, and rebloom count.

---

*Next: [Complete Examples](./14-examples.md)*
