# Gold labels — human-authored only

`gold_labels.jsonl` calibrates the model-graded grounding scorer. It is written
by hand by the author. An agent must not write to it, and a `PreToolUse` hook
blocks attempts (AGENTS.md §5).

Labels are agent-written only in the sense that they must not be: if a model
both produces the generation and labels it, calibration measures two model
outputs agreeing with each other, and the judge's bias goes unmeasured.

## TODO(human)

Label ~20 claims from the frozen `gen_v0` run. That run is deliberately poor
copy, and that is correct — you are calibrating the judge, not the generator,
and obvious hallucinations make disagreement more diagnostic. Label it once and
never re-label against a later run.

## One record per line

```json
{
  "generation_sha256": "<sha256 of the exact generation text this claim came from>",
  "claim": "<the atomic claim, quoted from the generated copy>",
  "verdict": "supported | contradicted | unsupported | review_sourced",
  "note": "<optional: why, especially for the judgement calls>"
}
```

`generation_sha256` joins a label to the exact text it describes — never a case
id. Generation is uncached across runs, so a case id would silently attach the
label to different copy on a re-run (AGENTS.md §6).

`review_sourced` means the claim traces only to a guest review, not to the
structured input. It is reported separately and never folded into precision.
