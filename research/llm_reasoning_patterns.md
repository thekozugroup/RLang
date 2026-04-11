# LLM Reasoning Patterns Research
## For RLang Formal Reasoning Language Design

Research compiled April 2026 from academic papers, model documentation, and empirical analyses.

---

## 1. CORE REASONING PHASES (Macro-Structure)

All reasoning models follow a broadly similar phase structure, though terminology varies:

### The Four-Phase Model (DeepSeek R1 Thoughtology)
Source: Marjanovic et al., "DeepSeek-R1 Thoughtology" (arXiv:2504.07128)

1. **Problem Definition** - Reformulates and clarifies the question, identifies constraints
2. **Bloom Cycle** - Decomposes into subproblems, applies mathematical/logical inference
3. **Reconstruction Cycles** - Revisits assumptions, explores alternative paths
   - *Short Reconstruction (Rumination)* - revisiting prior decompositions without novel strategies
   - *Long Reconstruction (Rebloom)* - abandoning failed approaches for wholly new decompositions
4. **Final Decision** - Asserts a final answer with summary

### The Cognitive Stage Framework (Distilled Models)
Source: Structured Reasoning Traces research (emergentmind.com)

1. **Framing** - Sets up the problem space
2. **Exploration** - Tests hypotheses and approaches
3. **Verification** - Checks intermediate results
4. **Synthesis** - Assembles final answer

Lexical pivots (transition markers) signal stage transitions in the trace.

### The Three-Stage Efficiency Model
Source: Wei et al., "Stop Spinning Wheels" (arXiv:2508.17627)

1. **Insufficient Exploration Stage** - Not enough reasoning, answers likely wrong
2. **Compensatory Reasoning Stage** - Productive reasoning, correct answers typically emerge here
3. **Reasoning Convergence Stage** - Overthinking begins, accuracy can DECREASE

The transition from stage 2 to 3 is the "Reasoning Completion Point" (RCP) - the optimal place to stop.

---

## 2. SIX REASONING PATTERNS OF O1 (Micro-Patterns)

Source: Wu et al., "A Comparative Study on Reasoning Patterns of OpenAI's o1 Model" (arXiv:2410.13639)

| Pattern | Abbreviation | Description | Domain Prevalence |
|---------|-------------|-------------|-------------------|
| **Systematic Analysis** | SA | Analyzes inputs/outputs/constraints holistically, then selects algorithm/data structure | Coding |
| **Method Reuse** | MR | Recognizes problem as instance of known class, applies standard solution (e.g., shortest path, knapsack) | Math, Coding |
| **Divide and Conquer** | DC | Breaks complex problem into subproblems, solves each, combines | Math, Coding (PRIMARY) |
| **Self-Refinement** | SR | Assesses own reasoning mid-inference, detects errors, corrects | All domains (PRIMARY) |
| **Context Identification** | CI | Summarizes relevant aspects of provided context before reasoning | Commonsense |
| **Emphasizing Constraints** | EC | Explicitly tracks and enforces problem constraints throughout | Commonsense |

**Key finding**: DC and SR are the DOMINANT patterns - the main driver of o1's success. SR+DC account for the majority of reasoning behavior in math/coding.

---

## 3. DISTINGUISHING TRAITS ACROSS MODELS (LOT Taxonomy)

Source: Chen et al., "Your thoughts tell who you are" (arXiv:2509.24147)

The LOT (LLM-proposed Open Taxonomy) method can distinguish reasoning traces between models with 80-100% accuracy. Key findings:

- **Smaller models** more often fall into circular reasoning loops
- **Code-specialized models** sometimes use Python functions to solve math problems (tool-shaped reasoning)
- **Scale affects reasoning style**: distilled smaller models reason differently from their larger teachers
- **Aligning reasoning style** of smaller models to larger ones improves accuracy by 3.3-5.7% (causal link between style and performance)
- **Plan generation and re-evaluation** are critical steps for solving math problems (Bogdan et al. 2025)

---

## 4. METACOGNITIVE PATTERNS

Source: arXiv:2505.13763, "Language Models Are Capable of Metacognitive Monitoring"

### Self-Monitoring
- Models can predict whether they will answer correctly BEFORE producing the answer
- This "knowing what they know" capability is real but unreliable and inconsistent
- Models frequently report 100% confidence even when wrong (overconfidence)

### Backtracking Markers
The "aha moment" in DeepSeek R1 training: sudden increase in use of "wait" during reflections, marking genuine self-correction behavior.

Common backtracking lexical signals:
- "Wait..." / "Hmm..." / "Actually..."
- "Let me reconsider..."
- "No, that's not right..."
- "I made an error in..."

### Error Correction
- Self-correction works best when the model catches errors in the CURRENT reasoning step
- Trying to correct errors from much earlier in the trace is unreliable
- The CLEAR framework uses model-internal entropy to identify uncertain predictions

### Faithfulness Problem
Source: Anthropic, "On the Biology of a Large Language Model" (2025)
- The steps Claude 3.5 Haiku used to solve a simple math problem were NOT what it claimed it took
- LLMs give reasons that do not necessarily reflect their actual internal computation
- Multi-hop reasoning (e.g., "capital of the state containing Dallas") shows internal intermediate representations ("Texas") that CAN be traced and manipulated

---

## 5. UNCERTAINTY AND CONFIDENCE HANDLING

Source: arXiv:2509.24202, arXiv:2505.23845

### How Models Express Uncertainty
- Hedging expressions ("I think", "probably", "it seems like", "roughly")
- Allocating ~1,000 additional reasoning tokens improves linguistic confidence calibration
- Extended CoT reasoning helps models explore their distribution and surface uncertainty
- After reasoning, models read their own trace and summarize alternatives/uncertainty

### Problems
- Persistent overconfidence: models often claim 100% confidence on wrong answers
- Hedging language perception varies across readers (subjective)
- Fine-tuning encourages hedging but doesn't guarantee calibration
- Verbalized confidence often decorrelated from actual accuracy

### Implications for RLang
Uncertainty is a real phenomenon in model reasoning but poorly calibrated. A formal language should probably treat confidence as a first-class construct rather than relying on natural language hedging.

---

## 6. AGENTIC REASONING PATTERNS (Tool Use & Planning)

Source: arXiv:2601.12560, ACL 2025 Agentic Reasoning survey

### The ReAct Loop
The fundamental agent reasoning pattern:
```
Thought -> Action -> Observation -> Thought -> Action -> Observation -> ...
```

### Five Core Agentic Patterns
1. **Tool Use** - Selecting and invoking external tools with proper schemas
2. **Reflection** - Assessing execution results and adjusting strategy
3. **ReAct** - Interleaving reasoning with action in iterative loops
4. **Planning** - Decomposing tasks into sub-tasks with execution ordering
5. **Multi-Agent Collaboration** - Distributing work across specialized agents

### Tool Selection Reasoning
Three approaches:
- **Automated** - Model selects from fixed catalog based on task
- **Rule-based** - Predetermined tool selection logic
- **Learning-based** - Model learns optimal tool selection from experience

### Tool Execution Patterns
- **Sequential** - One tool at a time, results inform next choice
- **Parallel** - Multiple independent tools simultaneously
- **Iterative** - Same tool repeatedly with refined inputs

### Planning Architecture
- **Linear** - Sequential step-by-step plans (ReAct)
- **Hierarchical** - Plans broken into sub-plans (Plan-and-Execute)
- **Tree-structured** - Parallel exploration of alternatives (Tree of Thoughts)
- **Recursive** - Self-decomposing problems into smaller versions

### Reflection Mechanisms
After task completion or failure:
1. Agent reflects on entire execution trace
2. Identifies errors or inefficiencies
3. Stores reflection in memory
4. Informs future planning

---

## 7. OVERTHINKING AND WASTED TOKENS

### The Overthinking Problem
Source: Wei et al. (arXiv:2508.17627), multiple 2025 studies

**Primary drivers of overthinking:**
1. **Verification loops** - Repeatedly checking already-correct work
2. **Over-exploration** - Continuing to explore after finding the correct answer
3. **Rumination** - Revisiting prior decompositions without new strategies
4. **Infinite reflection loops** - "Wait, let me reconsider..." ad infinitum

### Quantified Waste

| Metric | Finding | Source |
|--------|---------|--------|
| DeepSeek R1-Zero thinking multiplier | ~11x more tokens in thought chains vs. final replies | Multiple analyses |
| Self-reflection token overhead | 27-51% of CoT tokens are explicit self-reflection ("Wait", "Hmm") that can be removed without accuracy loss | arXiv:2506.08343 |
| GPQA-D compression achievable | ~50% sequence compression with maintained accuracy | Wei et al. 2508.17627 |
| TALE-EP output token reduction | 67% token cost reduction, 59% expense reduction | ACL 2025 |
| Infinite loop incidence | 1.1-6.7% of problems enter infinite reasoning loops | Wei et al. on Qwen3-32B |
| SFT model repeat rate | Much higher than base or RL-tuned models | Zhang et al. 2505.07961 |

### The Sweet Spot Finding
There exists an optimal reasoning length:
- **Too short** = insufficient exploration, wrong answers
- **Moderate** = highest accuracy (the "sweet spot")
- **Too long** = accuracy DECREASES, resources wasted, possible infinite loops

"Longer thinking does not only not ensure better reasoning, but also leads to worse reasoning in most cases."

### Implications for RLang
- A formal reasoning language could enforce structured termination conditions
- Phase-tracking (which stage of reasoning am I in?) could prevent convergence-stage waste
- Explicit "I have enough information to conclude" markers could replace implicit ones

---

## 8. FAILURE MODES IN REASONING TRACES

### Common Failures
1. **Circular reasoning** - Returning to the same argument repeatedly (more common in smaller models)
2. **Faithless CoT** - Stating reasoning steps that don't reflect actual computation
3. **Premature commitment** - Locking into wrong approach early, not backtracking
4. **Constraint forgetting** - Losing track of problem constraints during long chains
5. **Fragile reasoning** - Semantically irrelevant perturbations degrade performance
6. **Pattern matching masquerading as reasoning** - Next-token prediction dressed as logical deduction
7. **Infinite reflection loops** - Self-correction triggers that never terminate
8. **Wrong answer persistence** - Finding correct answer early but continuing to explore until finding a wrong one

### Structural Vulnerabilities
Source: Apple ML, "The Illusion of Thinking" (2025)
- For long tasks requiring genuine multi-step problem-solving, transformers lose track of key information
- Default to training data patterns rather than genuine reasoning
- Chain-of-thought is still fundamentally next-token prediction

---

## 9. INTERNAL REASONING vs. VISIBLE REASONING

Source: Anthropic circuit tracing research (2025)

### Key Discovery
Models perform significant reasoning DURING the forward pass, not just in visible CoT:
- **Forward planning**: considering multiple possibilities in advance
- **Backward planning**: working backwards from goal states
- **Hidden intermediate representations**: e.g., internally representing "Texas" when asked about "capital of state containing Dallas"

### Implications
- Visible reasoning traces are an INCOMPLETE picture of model cognition
- The trace is partly faithful, partly confabulated
- A formal reasoning language should account for the gap between stated and actual reasoning

---

## 10. SYNTHESIS: PATTERNS FOR RLANG DESIGN

### Productive Reasoning Patterns (worth formalizing)
1. **Problem decomposition** (DC) - splitting into subproblems
2. **Constraint tracking** (EC) - maintaining awareness of requirements
3. **Method selection** (MR/SA) - choosing appropriate solution strategies
4. **Verification** (bounded) - checking work once, not repeatedly
5. **Context extraction** (CI) - identifying relevant information
6. **Self-correction** (SR, bounded) - catching and fixing errors
7. **Planning** - structuring multi-step execution
8. **Tool invocation** - selecting and using external capabilities

### Wasteful Patterns (worth preventing or limiting)
1. **Rumination** - revisiting without new insight
2. **Over-verification** - checking the same thing repeatedly
3. **Confidence theater** - expressing uncertainty without information gain
4. **Circular reasoning** - returning to previously explored dead ends
5. **Premature conclusion exploration** - continuing after answer is found
6. **Hedging filler** - "Let me think about this..." without productive content
7. **Infinite reflection** - unbounded self-correction loops

### Estimated Token Efficiency
Based on the research:
- **Productive reasoning**: roughly 40-60% of tokens in a typical extended reasoning trace
- **Self-reflection overhead (removable)**: 27-51% of tokens
- **Outright waste (loops, repetition)**: 1-7% of tokens in well-trained models, higher in SFT models
- **Structural/transition tokens**: 10-20% (problem restatement, framing, formatting)

The most efficient reasoning traces are moderate length, use DC+SR patterns, and terminate at the Reasoning Completion Point.

---

## KEY REFERENCES

### Academic Papers
- Marjanovic et al. (2025) - "DeepSeek-R1 Thoughtology" - arXiv:2504.07128
- Wu et al. (2024) - "Comparative Study on Reasoning Patterns of OpenAI's o1" - arXiv:2410.13639
- Chen et al. (2025) - "Your thoughts tell who you are" (LOT Taxonomy) - arXiv:2509.24147
- Wei et al. (2025) - "Stop Spinning Wheels" (Overthinking) - arXiv:2508.17627
- Zhang et al. (2025) - "Understanding Token-Efficiency of Reasoning Models" - arXiv:2505.07961
- arXiv:2505.13763 - "Language Models Are Capable of Metacognitive Monitoring"
- arXiv:2506.08343 - "Wait, We Don't Need to Wait" (Removing thinking tokens)
- arXiv:2509.24202 - "Can Large Language Models Express Uncertainty Like Human?"
- arXiv:2601.12560 - "Agentic AI: Architectures, Taxonomies, and Evaluation"

### Industry/Lab Research
- Anthropic (2025) - "On the Biology of a Large Language Model" - transformer-circuits.pub
- Anthropic (2025) - "Tracing Thoughts of a Language Model"
- OpenAI (2025) - Reasoning Models documentation - platform.openai.com
- Apple ML (2025) - "The Illusion of Thinking"

### Surveys
- ACL 2025 - "A Survey of Chain-of-X Paradigms for LLMs"
- arXiv:2502.12289 - "Evaluating Step-by-step Reasoning Traces: A Survey"
- arXiv:2508.17692 - "LLM-based Agentic Reasoning Frameworks: A Survey"
