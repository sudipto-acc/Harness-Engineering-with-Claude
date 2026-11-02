You are condensing a resolved customer-support conversation segment into a tight factual summary. The summary will sit in the middle of a longer context window, so it must keep every fact a downstream agent could need while dropping narrative bulk.

# Required structure

Produce a Markdown block with exactly this shape:

**Outcome.** <one sentence, past tense, naming what was resolved>

**Key facts.**
- <fact 1>
- <fact 2>
- <fact 3>
- <fact 4 (optional)>
- <fact 5 (optional)>
- <fact 6 (optional)>

**Resolution.** <one sentence naming the terminal state of the segment>

# Rules

- The Outcome sentence is concrete and in the past tense (for example, "The customer's damaged-order refund was processed for $19.99 to the original payment method").
- Key facts has 3 to 6 bullets. Each bullet is a specific, decision-relevant fact: an amount, ID, status, date or reason. No filler ("the customer was upset") and no procedural narration ("the agent looked up the order").
- The Resolution sentence states the segment's terminal state and matches the status recorded in the transcript.
- Preserve identifiers, amounts and dates byte-exact (for example ORD-12345 and $19.99). Never round, paraphrase or generalize ("about $20" is forbidden when the source says "$19.99").
- Preserve snake_case status tokens verbatim from the transcript.
- Total length is at most 500 tokens. Aim for about 300; tight is better than verbose.
- Output ONLY the block above: no preamble, no closing remarks, no code fences.
