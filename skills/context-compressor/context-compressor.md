---
id: context-compressor
name: context-compressor
category: uncategorized
tags: []
author: opencode-core
version: 1.0.0
description:
---

---
id: context-compressor
file_path: skills/context-compressor.md
name: Context Compressor
category: ai-ops
tags: [context-window, token-optimization, summarization, conversation-memory]
author: opencode-core
version: 1.0.0
description: Compress long conversation histories or documents to save context window token limits.
---

# Context Compressor

## Prerequisites & Dependencies
- Python 3.10+ with `pip install tiktoken openai`
- Model provider API key for summarization (a cheap, fast model suffices)
- Known token budget of the target model (e.g., 128k window; plan for 60-70% utilization to reserve space)

## Execution Steps
1. Measure token count of the full context with the model's tokenizer, computing headroom against the budget while reserving tokens for the system prompt and expected output.
2. Segment the context into compression units: per-turn conversation pairs, per-file code blocks, per-document sections.
3. Classify each unit as verbatim (active task code, explicit constraints, accepted decisions, last N turns) or compressible (exploration output, verbose tool logs, already-resolved debugging).
4. Summarize compressible units with a fixed extraction template (topic, outcome, constraints, open questions); prefer maps/diffs over free prose.
5. Reassemble in order: pinned verbatim units first, followed by compact summaries, then the most recent verbatim turns; oldest-to-newest ordering preserves recency bias.
6. Verify: compare total token count against budget and run a faithfulness check — does a fresh model answer key questions from the original content correctly using the compressed version?

```python
import tiktoken
from openai import OpenAI

enc = tiktoken.encoding_for_model("gpt-4o")
count = lambda s: len(enc.encode(s))

TEMPLATE = ("Compress into terse notes. Keep: decisions, constraints, code identifiers, "
            "open questions. Drop: pleasantries, repetition, failed attempts.\n\n{text}")

def compress(units: list[str], budget: int, client: OpenAI) -> list[str]:
    out, used = [], 0
    for u in units:
        if count(u) <= 120:  # keep short verbatim units as-is
            kept = u
        else:
            kept = client.chat.completions.create(
                model="gpt-4o-mini", temperature=0,
                messages=[{"role": "user", "content": TEMPLATE.format(text=u)}],
            ).choices[0].message.content
        if used + count(kept) > budget:
            break
        used += count(kept); out.append(kept)
    return out
```