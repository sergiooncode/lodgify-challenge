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

Phases 0–1 of `PLAN.md` are complete. Built: the two-layer schema and its
adapter, configuration, fixtures, the cost model, the gold-label container and
its write guard, and a notebook that runs offline against a real committed log.

**Not yet built:** the generator and every scorer. Sections below marked TODO are
honest placeholders, not oversights.

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

### Why each claim is verified in its own call

Verification could send every extracted claim to the judge in one request. That
is cheaper — roughly $0.15 per epoch against $0.29, and about 40 calls against
600 across the full two-version sweep. It was rejected anyway, because the
saving buys three problems and the difference is single-digit dollars.

**Judgements stop being independent.** Fifteen claims in one context means an
early verdict anchors the ones after it, and the model drifts toward internal
consistency across the batch. Whatever the judge is measuring then, it is not
fifteen separate assessments — and self-consistency across repeats, one of the
two calibration numbers, would be measuring the batch rather than the judgement.

**Truncation becomes all-or-nothing.** One long JSON response that hits the
token ceiling is unparseable, and every claim in that sample collapses to
`unsupported`. Per-claim, the same failure costs one claim. Both fail closed,
but one loses a data point and the other silently reports a property as
completely ungrounded.

**Joining verdicts back to claims is fragile.** A batched response has to
identify which claim each verdict belongs to. Matching on claim text breaks the
moment the judge lightly rewords one, and the claim then defaults to
`unsupported` — a measurement error wearing the costume of a conservative
default. Index-based joining fixes the obvious case and still depends on the
judge numbering correctly. Per-claim, the question does not arise.

The cost is real but small; the measurement validity is the deciding factor.
Claims within a sample are verified concurrently, so wall-clock scales with the
slowest claim rather than their number — the 15× is in call volume and rate
limits, not in latency.

---

## Results

One frozen run of `gen_v0` over four properties, scored by seven deterministic
checks and the grounding metric. Every number below is read from the committed
log and reproduced by `evals.ipynb` with no API key.

### Grounding

| metric | value |
|---|---|
| precision | **0.61** (± 0.08) |
| recall | 0.83 |
| review-sourced rate | 0.07 |

Roughly two in five first-party claims are not supported by the structured
input. `gen_v0` is deliberately mediocre — it is told to be vivid and never told
to stay grounded — so this is the metric working, not the generator failing
unexpectedly.

**The fourth verdict earns itself immediately.** On the realistic property, five
claims trace only to guest reviews: the five-minute walk to the beach, that the
*bedrooms* are air-conditioned, that the street is quiet, that a welcome bottle
of wine is left out. Counted as supported, that property's precision would read
0.90 instead of 0.81 — and the fact that the owner is republishing guests'
opinions as their own marketing claims would be invisible.

**Sparse input produces more hallucination, not less.** The sparsest fixture —
one amenity, no reviews, null policies — scored the *worst* precision (0.45)
while covering every key fact it had (recall 1.00). Given almost nothing to say,
the model filled the space from world knowledge: a Belle Époque market
restoration, azulejo-tiled streets, port wine cellars across the Douro. None of
it is in the input. The practical implication is that thin listings, which are
exactly the ones an owner most wants help with, are the ones where generated
copy is least trustworthy.

**Two judge calls worth noting**, because they show the instrument is discriminating
rather than pattern-matching: "rated across 87 stays" was rejected, since the
input records 87 *reviews*; "the bathrooms have full laundry facilities" was
rejected as over-reading a `BathroomAndLaundry` amenity code.

**And one likely judge error:** "the terrace has sea views" was marked
unsupported although the owner's own headline reads "Hillside villa with sea
views". This is exactly what Phase 5's human labels exist to catch, and it is
why precision above is a number from an instrument that has not yet been
calibrated.

### Judge calibration

Precision means nothing without knowing how far the judge can be trusted, so it
is measured two ways. **Bias** — does it systematically disagree with a person?
**Variance** — does it give the same answer twice? A judge can be perfectly
stable and stably wrong, or unbiased on average and useless per claim.

| | value |
|---|---|
| agreement with human labels | 17/18 = **0.94** |
| Cohen's kappa | **0.91** |
| self-consistency (3 passes, 94 claims) | **0.94** stable |

Kappa matters more than raw agreement: the verdict distribution is skewed, and a
judge that answered "unsupported" every time would score respectably on the raw
figure. 0.91 says the agreement is not coming from the marginals.

**The honest reading is "high", not "0.94".** With 18 labels the exact 95%
interval on raw agreement is **[0.73, 1.00]**. Eighteen labels can show broad
alignment; they cannot fix the number to two decimal places.

Two things constrain how far these numbers generalise. The labelled sample is
**stratified** — up to two claims from each verdict class per property — because
uniform sampling of ~90 claims would have yielded about one review-sourced claim
and left the category the design turns on unmeasurable. That makes it a
deliberately hard subset, not a typical one. And there is **one labeller**, so a
disagreement cannot be separated into "the judge is wrong" versus "this claim is
genuinely ambiguous".

#### What the judge is not trustworthy for

The single disagreement was not random, and a controlled probe confirmed it as a
systematic blind spot. The human labelled "Wren Cottage is on the edge of Haworth
Moor" unsupported: the owner wrote "on the edge of the moor" and gave the town as
Haworth, and chaining those into a named landmark asserts something the owner
never did. The judge called it supported.

That claim was confounded with a distance claim in the other example, so five
probe claims were judged directly:

| claim | judge |
|---|---|
| "near **Mercado do Bolhão**" (name inferred from the property's name) | supported |
| "near a market" (the owner's own words) | supported |
| "**steps from** a market" (distance) | unsupported |
| "on the edge of **Haworth Moor**" (name inferred from town) | supported |
| "on the edge of a moor" (the owner's own words) | supported |

**The judge reliably rejects distance claims and reliably accepts inference to a
named landmark.** It is trustworthy for claims that are flatly present or flatly
absent from the input, and for the price/availability/distance family. It is not
trustworthy for specificity smuggled in by inference — a property called
"Apartamento Bolhão" that is "near the market" becoming "near Mercado do Bolhão",
which is precisely how a listing earns a complaint when the guest finds a
different market.

The consequence for the headline number: **precision 0.61 is an upper bound.**
Every known judge error runs in the permissive direction, so a stricter standard
would score `gen_v0` lower, not higher.

#### Where the judge is unstable

Six of 94 claims changed verdict across three passes. They cluster rather than
scatter:

- claims about the **absurd-value fixture**, where the input is degenerate —
  "the lodge is spacious" went supported, supported, contradicted with
  `bedrooms: -2` and `max_guests: 0`
- claims sitting on the **inference boundary** — "close to walking routes onto
  the moor" flipped, which is the same fault line as the disagreement above
- one **precision-of-wording** case — "the rating is based on 87 stays" when the
  input records 87 *reviews*

Instability concentrating on degenerate input and on the boundary is more
reassuring than uniform noise would be: it says the judge is stable where the
answer is clear and wobbles where a person would also hesitate.

#### A limitation of the verdict scheme itself

The four verdicts collapse "invented from nothing" and "reasonably inferred but
never stated" into `unsupported`. Those are different failures. The collapse is
deliberate here — the owner publishes this copy and warrants it, so an unverified
inference is a liability rather than a near-miss — but it means precision
penalises reasonable inference exactly as hard as fabrication. A fifth verdict
(`inferred`) would separate them, and the calibration above suggests that is
where the judge and a careful human diverge most.

### Deterministic checks

| check | accuracy |
|---|---|
| required_sections | 1.00 |
| headline_is_one_line | 1.00 |
| placeholder_leakage | 1.00 |
| high_value_field_coverage | 1.00 |
| discriminatory_language | 0.75 |
| unverifiable_superlatives | 0.50 |
| unsupportable_by_construction | 0.25 |

Three of four properties claim a distance the schema has no field for — "steps
from", "a short stroll", "a five-minute walk". The sparse fixture produced
"perfect for couples", which is Fair-Housing-style steering and a legal exposure
for the owner publishing it, not a grounding problem at all.

These cost nothing: they re-run against the frozen generations with no API call,
which is why they run before anything model-graded.

The format check scores 1.00 across the board. It is a regression guard, not a
discriminator — worth keeping and worth not mistaking for a quality signal.

---

## How the tests are checked

54 tests, no network, no key. But a green suite says nothing about whether the
assertions would notice a bug, so the suite is graded two ways.

**Coverage** — 97%, and the gap is honest: `tasks.py` holds the Phase 0 probe
task, exercised by a real run rather than by unit tests.

```bash
uv run pytest --cov=lodgify_challenge --cov-report=term-missing
```

**Mutation testing** — the one that actually answers "do these tests have
substance". It mutates the source (flips a comparison, swaps a constant, deletes
an argument) and reruns the suite; a mutation nobody notices marks a test that
would not catch the corresponding bug. Coverage cannot detect this, because a
test that calls a function and asserts nothing still covers every line.

```bash
uv run mutmut run && uv run mutmut results
```

Currently **13 of 225 mutants survive, with none uncovered** — the survivors are
in loop details and the token-counter adapter, where the mutation changes nothing
a caller can observe.

It earned its keep immediately. Two real gaps, both invisible to a green suite
and to 93% coverage:

- **Replacing every policy field with `None` survived.** The adapter tests only
  asserted policies were `None` on the sparse fixture, so an adapter that
  silently dropped all policy data would have passed.
- **`grounding_profiles` had no tests at all** — 66 uncovered mutants in the very
  function that produced the cost projections used to make a real decision.

Running it also surfaced a genuine design bug rather than a test gap: `REPO_ROOT`
was derived from `__file__` by package depth, which breaks whenever the package
is copied or installed elsewhere. It now locates the repo by its `pyproject.toml`.

> The mutation sandbox copies the package but not `data/`, so the run needs
> `ln -sfn ../data mutants/data` after the first invocation.

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

**Agent test-quality gaps caught by tooling, not by review:** mutation testing
found that the adapter tests would not have noticed policy data being dropped
entirely, and that `grounding_profiles` — the function behind the cost
projections — had no tests at all. Both were agent-written and both looked fine
under a green suite at 93% coverage.

**Agent errors caught in review:** a claimed "parent directory `.env` leak" that
the evidence did not support and was retracted; a verification script that
silently passed while skipping five of six checks; a first notebook run that
appeared to prove keyless execution but had in fact loaded the key from
`.env.local`.
