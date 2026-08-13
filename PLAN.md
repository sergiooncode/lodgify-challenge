# PLAN.md

Phased checklist. Read at the start of each task. Keep one end-to-end path
runnable at all times and thicken it — do not build horizontally and branch
ahead. Tick boxes as acceptance criteria are met.

If time runs short, cut in this order: Bonus, then Phase 6 (the v1 iteration —
the only expensive generator work left), then the tail of Phase 3's scorer list.
Phases 3b, 4, 5, 7 and 8 are not cut; they are the submission. The evaluation
suite (Phases 3–5 and 7) and the README/notebook narrative (Phase 8) are what is
being graded.

Most of the eval suite does not need the generator. Phase 3's scorers are unit
tested against hand-written strings with no network, so they can be built before
`gen_v0` is any good. That, more than phase order, is what protects the time.

Budget: 3–4 focused hours.

**Gate, not a suggestion:** if one property is not scored end to end (Phase 2) by
the 90-minute mark, stop building scaffolding — cut to three fixtures and move
on. Nothing in Phase 0–1 gets built ahead of what Phase 2's single slice needs.

**API budget: not the binding constraint.** Modelled in `cost.py` against
measured fixture sizes (mean 536 tokens). On Sonnet 5, four fixtures through
generate → extract → verify costs ~$0.15 for one epoch; the full Phase 6 sweep of
two versions at five epochs is ~$1.53 batched or ~$2.88 verifying each claim
separately. Allowing for the dozen-plus re-runs that development actually takes,
the whole project lands around $3–8. Opus would be ~1.7× that and still small.

So the model choice is a quality decision, not a budget one, and epochs are
affordable. What actually constrains the run is wall-clock time and rate limits.
The token sizes behind these figures are assumptions apart from the property
itself — re-derive them from the first real log rather than trusting them.

---

## Phase 0 — Spike: prove the Inspect replay path (do this first, ~20 min)

The riskiest unknown is the brief's "reproducible with no API calls" requirement.
Settle it before building anything real.

- [x] `uv init` (Python 3.13), add `inspect-ai` + `anthropic`
- [x] Trivial Task: one hand-written Sample, `generate()` solver, `includes()`
      scorer. Run it once against the real model to produce a `.eval` log.
      `replay_probe` in `tasks.py`; mechanism proved first against `mockllm`
      (that log deleted, never committed) and then for real on Sonnet 5
- [x] Confirm how a committed `.eval` log is re-read with **no API call**.
      `list_eval_logs` + `read_eval_log` return task, model, status, scores and
      sample output with the key unset. `.eval` is a zip archive, not text
- [x] Epochs: `config.epochs` is recorded and every sample carries its own
      `epoch` field, so per-sample results are already separable
- [ ] Cache: `input_tokens_cache_write` / `input_tokens_cache_read` are in the
      log but were 0 — caching is **opt-in**, not automatic. Phase 4's "re-run
      hits the cache, no second API call" needs `generate(cache=True)` and is
      still unproven
- [ ] Ship logs from a **clean tree**. The log embeds `revision.commit`, and
      this first one recorded `dirty: true`, so its commit does not identify the
      code that produced it. Provenance is the point of committing logs at all
- [x] The `inspect eval` CLI does its own `.env` lookup and does not see
      `.env.local` — it failed with "No ANTHROPIC_API_KEY defined". Real runs go
      through `load_settings().export()`; document that, or add a thin entry
      point, before anyone else tries the bare CLI

**Acceptance:** a notebook cell reads a committed `.eval` log and shows results
with `ANTHROPIC_API_KEY` **unset** — no raise, no network. That is the reviewer's
actual environment, so it is the criterion. Re-tested as written at Phase 8. If
this doesn't work the way the brief assumes, everything else changes — so it's
first.

---

## Phase 1 — Skeleton + data model

- [x] `pyproject.toml`, package layout, `CLAUDE.md` importing `@AGENTS.md`
- [x] `PropertyListing` canonical model — shape not plausibility (AGENTS §4)
- [x] Raw schema type matching the brief's object exactly, in an adapters module;
      `to_listing()`. Raw field names appear nowhere else — enforced by two
      structural tests (AST import scan, and a grep for brief-only field names)
- [x] Amenity + `property_type` code→label vocabulary, hand-authored, living with
      the adapter and exported for the Phase 4 scorer. Covers only the codes the
      fixtures actually use — not an exhaustive map. Labels are minimal and
      literal: `InternetBroadband` → "broadband internet", never "free
      high-speed WiFi"; `NormalApartment` → "apartment". Every adjective the map
      does not license is a hallucination Phase 4 must catch
- [x] PreToolUse hook blocking writes to the gold-labels file
- [x] Three or four synthetic fixtures, including the adversarial slice (one
      injection, one absurd-value). Load-bearing, not polish: Phase 7 is a
      protected phase *because* it is nearly free, and it is only free if the
      slice already exists. Author it later and Phase 7 stops being cheap

**Acceptance:** fixtures load and validate; `bedrooms: -2` parses without error;
a structural test confirms raw types import only inside adapters. The vocabulary
is input data and the scorer's ground truth — never something the generator
invents at runtime.

---

## Phase 2 — First vertical slice: one scorer end to end

The point is to see a real score immediately, before the generator is any good.

- [x] `gen_v0` solver: deliberately mediocre prompt, produces the four sections
- [x] One deterministic scorer (format) wired into a Task
- [x] Run the Task; open the log. 4 samples, format accuracy 1.000, ~$0.05 —
      within 10% of the cost model's projection
- [x] **Freeze this run over all fixtures and keep it.** Phase 5's hand labels
      are written against it, and hand-labelling is the one serial, human-blocked
      task in the plan — starting it late is how calibration gets cut

Findings from this run are written up in the README.

---

## Phase 3 — Deterministic scorers

- [x] Base `DeterministicCheck` class with a concrete subclass per check, in
      `checks.py`. `scorers.py` is a thin adapter to Inspect, so the hierarchy
      sits on top of Inspect rather than competing with it
- [x] Format: four sections present, headline fits its single-line slot
- [x] Placeholder leakage / unfilled templates
- [x] Unverifiable superlatives
- [x] Unsupportable by construction: price, availability, proximity
- [x] Fair-Housing-style discriminatory language
- [x] Coverage: were high-value input fields used?

**Acceptance met:** unit tests against fixed strings, no network. All seven
re-scored the frozen run with zero API calls. Results in the README.

---

## Phase 3b — Tests as a deliverable

The brief names dependency injection, inheritance, and mocking explicitly. This
is graded work, not a byproduct of Phase 3.

- [x] Scorer subclasses tested against fixed strings — exercises the hierarchy,
      not just the leaves
- [x] Model access injected; the model-graded scorer tested against a mock
      client that returns canned verdicts
- [x] Adapter tests: garbage survives intact, nothing clamped or repaired

**Acceptance:** `uv run pytest` is green with `ANTHROPIC_API_KEY` unset. A test
that needs a key is written wrong (AGENTS §4).

---

## Phase 4 — Grounding scorer (headline metric)

- [x] Claim extraction from generated copy → atomic claims
- [x] Verify shape decided: **one call per claim**, not batched. The batched
      path was removed rather than kept as a dead alternative; the reasoning
      is written up in the README
- [x] Verify each claim: supported / contradicted / unsupported / review-sourced
- [x] Review-sourced reported separately, never folded into precision
- [x] Aggregate precision + recall over the first three categories

**Acceptance met**, scored against the frozen Phase 2 generations rather than a
fresh run — generations byte-identical, only judging paid for. Results in the
README. Cache reuse remains unproven (see Phase 0).

---

## Phase 5 — Judge calibration (HUMAN WORK)

- [x] `TODO(human)`: 18 claims hand-labelled from the frozen Phase 2 run. Not
      agent-generated (AGENTS §5)
- [x] That run is `gen_v0`'s deliberately-bad output, and that is correct — you
      are calibrating the judge, not the generator. Obvious hallucinations are
      easier to label and make disagreement more diagnostic. Do not wait for a
      "good" run to label. Label v0 once and never re-label against a later run:
      the labels join by hash of the generation text (AGENTS §6), so re-labelling
      orphans them and silently invalidates every agreement number
- [x] Judge vs hand labels → agreement (bias): 0.94, kappa 0.91, n=18
- [x] Judge vs itself across repeats → self-consistency: 0.94 over 3 passes
- [x] What the judge is and isn't trustworthy for — written up in the README,
      with a controlled probe isolating the inference blind spot

**Acceptance:** both numbers reported together with a plain statement of what
stays unmeasured.

---

## Phase 6 — Iterate v0 → v1 (→ v2 if time)

- [x] `gen_v1`: fix the dominant failure v0's scores exposed
- [x] Results table: metric per version with confidence intervals
- [x] Paired significance test — did it help, or is it noise?

**Acceptance:** each version names the failure it targets; a change that didn't
help stays in the table, reported honestly. If short on time, v1 only.

---

## Phase 7 — Adversarial + injection report

- [x] Scores broken out: adversarial slice vs realistic slice
- [x] Injection cases: does owner text steer the output? State the outcome even
      if it fails
- [ ] Any mitigation, and its cost — **not done.** No mitigation was built or
      costed. The report states the vulnerability and its bound instead

**Acceptance:** injection result stated explicitly. A reported vulnerability
beats a silent one.

---

## Phase 8 — Notebook + README

- [x] `evals.ipynb` runs the pipeline top to bottom and reads the committed logs
- [x] README: approach, `uv sync` run steps, how to read the logs, how AI was used
- [x] Notebook narrative: assumptions/scope up top; each metric justified in
      customer terms; trade-offs + roads-not-taken at the end (JSONL-vs-DB is
      moot now — instead: why these metrics, why Inspect, what breaks at scale,
      online signal = owner edit-rate)
- [x] State plainly: if the generator emits JSON via tool use, the format scorer
      passes by construction. Keep it as a regression guard, but name
      constrained decoding — not prompt quality — as what passes it
- [x] "What I did not build and why": RAG, fine-tuning, agents, serving, and
      `image_urls` (no vision — scoped out on the record, not silently dropped)

**Acceptance:** a reviewer running `uv sync` reproduces results offline and, from
the notebook alone, understands what was measured and how much to trust it.

---

## Bonus (only if 1–8 done)

- [ ] Second model tier on the same scorers
- [ ] Bootstrap CIs / effect sizes
- [ ] More adversarial categories

## Explicitly cut (name in README)

RAG, retrieval eval, fine-tuning, agent frameworks, chatbot, serving,
observability infra, image analysis (`image_urls` unused — no vision).
