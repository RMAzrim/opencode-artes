---
id: prompt-evaluator
file_path: skills/prompt-evaluator/prompt-evaluator.md
name: Prompt Evaluator
category: ai-ops
tags: [prompt-engineering, llm-evaluation, accuracy, token-budget, benchmarking]
author: opencode-core
version: 1.0.0
description: Evaluate agent prompt effectiveness using accuracy metrics and token constraints.
---

# Prompt Evaluator

## Prerequisites & Dependencies
- Node.js 18+ with `npm i -g promptfoo`, or Python 3.10+ with `pip install tiktoken openai` for token accounting
- Provider API key for the model under evaluation (e.g., `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`)
- A golden evaluation dataset of 20-50+ examples: `{input, expected_output}` pairs with optional category tags

## Execution Steps
1. Define success criteria up front: task accuracy (exact match, similarity, or LLM-graded rubric), format compliance, latency, and a hard max-token budget per completion.
2. Build the evaluation dataset and encode assertions; prefer deterministic checks (contains, regex, JSON schema) over model-graded ones.
3. Set up the baseline prompt as variant A and register candidate variants B, C, ... in the eval matrix.
4. Run the harness across all variants at `temperature: 0`, recording accuracy, tokens used, and cost per test case.
5. Analyze failures per variant: categorize errors (instruction drift, format break, hallucination) and flag any variant exceeding the token budget.
6. Iterate on the dominant error category, re-run, and promote a variant only if it improves accuracy without regressing the token budget or other categories.

```yaml
# promptfooconfig.yaml
prompts:
  - id: baseline
    raw: "Answer concisely: {{question}}"
  - id: v2
    raw: "You are a precise assistant. Answer in <=30 words.\nQuestion: {{question}}"
providers: [openai:gpt-4o-mini]
tests: data/cases.json
defaultTest:
  options: { provider: { config: { temperature: 0 } } }
```

```bash
promptfoo eval
promptfoo view
```
