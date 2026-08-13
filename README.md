# lodgify-challenge

An evaluation-first pipeline that turns vacation-rental property data into
structured marketing copy — hero headline, highlights, "about this place", and
amenities descriptions.

**The evaluation suite is the deliverable, not the generator.** Where "better
copy" and "better measurement of copy" conflict, measurement wins.

The motivating risk: sparse, owner-supplied, sometimes untrusted property data
becomes copy a property owner publishes under their own name. A hallucinated
"private pool" means guest complaints, refunds, and a damaged listing. Every
claim in generated copy must trace back to the input.

---

## Status

Phases 0–1 of `PLAN.md`. Built: configuration, fixtures, the cost model, the
gold-label container and its write guard, and a notebook that runs offline.

**Not yet built:** the generator, any scorer, and the committed `.eval` logs.
Sections below marked TODO are honest placeholders, not oversights.

---

## Running it

Requires Python 3.13 and [uv](https://docs.astral.sh/uv/). No other setup.

```bash
uv sync
```

**Tests** — the gate is green with no API key present:

```bash
uv run pytest
```

**The notebook** — runs top to bottom against committed artifacts, no API calls:

```bash
uv run jupyter execute --inplace evals.ipynb   # headless
uv run jupyter lab evals.ipynb                 # interactive
```

To reproduce a reviewer's environment exactly on a machine that *does* have a
key, point the env-file lookup at nothing:

```bash
LODGIFY_ENV_FILE=/nonexistent uv run pytest
LODGIFY_ENV_FILE=/nonexistent uv run jupyter execute --inplace evals.ipynb
```

### Generating (needs a key)

Only regeneration needs credentials. Put the key in `.env.local` (gitignored;
see `.env.example`):

```
ANTHROPIC_API_KEY=sk-ant-...
```

Note that Inspect's own dotenv lookup walks up the directory tree looking only
for `.env`, so which file it finds depends on where the process started.
`lodgify_challenge.config` reads one explicit path instead and hands back an
injected settings object.

---

## Reading the logs

TODO — pending the first real run. The committed `.eval` logs under `logs/` are
the graded artifact. They come from real runs against the real model; the mock
client in the test suite exists so tests run without a key and never produces a
log that ships.

The command and its flag are verified present (`inspect` 0.3.258); what is not
yet proven is the round trip against an actual log, since none exists:

```bash
uv run inspect view --log-dir logs
```

The notebook also reads them programmatically via `inspect_ai.log`.

---

## Approach

TODO — written once there are results to describe. The design commitments are
recorded in `AGENTS.md` (invariants) and `PLAN.md` (phases and acceptance
criteria). In short:

- **Grounding is the headline metric.** Claims are extracted from generated copy
  and checked against the structured input, resolving to one of four verdicts:
  supported, contradicted, unsupported, or **review-sourced**. Review-sourced
  claims trace only to a guest review; they are reported separately and never
  folded into precision, because an owner republishing a guest's opinion as a
  first-party marketing claim is a distinct risk from inventing one.
- **Deterministic before model-graded.** Format, placeholder leakage, banned
  phrasing, and claims that are unsupportable by construction (price, rates,
  availability, distance to landmarks have no schema field at all) are caught
  with no API call.
- **The judge is calibrated, not assumed.** Its agreement with human labels and
  its self-consistency across repeats are both reported.

---

## Cost

`src/lodgify_challenge/cost.py` models projected spend before it is spent, with
an injected token counter so tests stay offline.

Measured against the four fixtures on Sonnet 5 (mean 536 tokens per property):
one epoch through generate → extract → verify is about $0.15 batched, and the
full two-version, five-epoch sweep is about $1.53. Realistically the whole
project costs single-digit dollars.

The conclusion that matters: **cost is not the binding constraint** — wall-clock
time and rate limits are. Model choice is therefore a quality decision. Every
token size except the property itself is an assumption and should be re-derived
from the first real log.

---

## Scope: what I did not build, and why

- **RAG and retrieval eval** — no corpus to retrieve from; the input is a single
  structured object.
- **Fine-tuning** — the failure mode here is grounding, which is measured and
  prompt-addressable. Fine-tuning would obscure that.
- **Agent frameworks, chatbot, serving layer** — out of scope for an offline
  evaluation deliverable.
- **Observability infrastructure** — Inspect owns logging, caching, and replay.
  A parallel run log would be a defect, not a feature.
- **Image analysis** — `image_urls` is in the brief's schema and deliberately
  unused. Nothing here does vision, so no claim is ever derived from an image.

---

## How AI was used

Kept as a running note, because it cannot be reconstructed honestly at the end.

**Agent-written, human-reviewed:** `config.py`, `cost.py`, the test suite, the
four fixtures, `evals.ipynb`, `.gitignore`, the `PreToolUse` hook, and the
edits to `PLAN.md` and `AGENTS.md`.

**Human-authored, not agent-generated:**

- `AGENTS.md` and `PLAN.md` — written first, and treated as the constitution the
  agent works under rather than output it produces.
- Every substantive design ruling: the cut order that protects the adversarial
  phase; freezing a run early so labelling can start; treating the amenity
  code→label vocabulary as *input data* and the grounding scorer's ground truth
  rather than something the generator invents; the review-sourced fourth verdict;
  placing inheritance where it genuinely reduces duplication rather than to
  demonstrate it; and the rule that real runs make logs while mocks make tests
  pass, and the two never cross.
- **The gold labels.** `data/gold_labels.jsonl` is hand-written. A `PreToolUse`
  hook blocks agent writes to it, and that guard is tested — agent-written labels
  would make calibration two model outputs agreeing with each other.

**Rejected, and why:**

- Defaulting to Opus on cost grounds. The cost model later showed the difference
  was under a dollar, so the reasoning was wrong even though the choice may
  stand on quality grounds.

**Agent errors caught in review:** a claimed "parent directory `.env` leak" that
the evidence did not support and was retracted; a verification script that
silently passed while skipping five of six checks; a first notebook run that
appeared to prove keyless execution but had in fact loaded the key from
`.env.local`.
