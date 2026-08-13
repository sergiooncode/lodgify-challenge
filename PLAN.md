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

---

## Phase 0 — Spike: prove the Inspect replay path (do this first, ~20 min)

The riskiest unknown is the brief's "reproducible with no API calls" requirement.
Settle it before building anything real.

- [ ] `uv init` (Python 3.13), add `inspect-ai` + `anthropic`
- [ ] Trivial Task: one hand-written Sample, `generate()` solver, `includes()`
      scorer. Run it once against the real model to produce a `.eval` log
- [ ] Confirm how a committed `.eval` log is re-read with **no API call**
      (`inspect view`, and the log/dataframe API in the notebook). Write the
      exact reproduction command into the README stub
- [ ] Confirm Inspect's model-output cache behaviour and how epochs record
      per-sample results

**Acceptance:** a notebook cell reads a committed `.eval` log and shows results
with `ANTHROPIC_API_KEY` **unset** — no raise, no network. That is the reviewer's
actual environment, so it is the criterion. Re-tested as written at Phase 8. If
this doesn't work the way the brief assumes, everything else changes — so it's
first.

---

## Phase 1 — Skeleton + data model

- [ ] `pyproject.toml`, package layout, `CLAUDE.md` importing `@AGENTS.md`
- [ ] `PropertyListing` canonical model — shape not plausibility (AGENTS §4)
- [ ] Raw schema type matching the brief's object exactly, in an adapters module;
      `to_listing()`. Raw field names appear nowhere else
- [ ] Amenity + `property_type` code→label vocabulary, hand-authored, living with
      the adapter and exported for the Phase 4 scorer. Covers only the codes the
      fixtures actually use — not an exhaustive map. Labels are minimal and
      literal: `InternetBroadband` → "broadband internet", never "free
      high-speed WiFi"; `NormalApartment` → "apartment". Every adjective the map
      does not license is a hallucination Phase 4 must catch
- [ ] PreToolUse hook blocking writes to the gold-labels file
- [ ] Three or four synthetic fixtures, including the adversarial slice (one
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

- [ ] `gen_v0` solver: deliberately mediocre prompt, produces the four sections
- [ ] One deterministic scorer (placeholder leakage or format) wired into a Task
- [ ] Run the Task; open the log
- [ ] **Freeze this run over all fixtures and keep it.** Phase 5's hand labels
      are written against it, and hand-labelling is the one serial, human-blocked
      task in the plan — starting it late is how calibration gets cut

**Acceptance:** one property → generated copy → one score, visible in the log.
Pipeline is runnable end to end. Everything after this thickens it. Labelling
can begin the moment this run exists, in parallel with Phases 3 and 4.

---

## Phase 3 — Deterministic scorers

- [ ] Base `Scorer` class with concrete subclasses — settled here, not
      retrofitted at the end. This is where the brief's inheritance requirement
      lives, so it shapes every scorer below it
- [ ] Format: four sections present, length bounds, valid structure
- [ ] Placeholder leakage / unfilled templates
- [ ] Banned phrasing + unverifiable superlatives
- [ ] Unsupportable by construction: price, rates, deals, availability, distance
      to landmarks. No schema field can ground any of these, so the check is
      exact and costs no model call
- [ ] Fair-Housing-style discriminatory language
- [ ] Coverage: were high-value input fields used?

**Acceptance:** each is a scorer with a unit test against fixed strings, no
network. All run before any model-graded scorer.

---

## Phase 3b — Tests as a deliverable

The brief names dependency injection, inheritance, and mocking explicitly. This
is graded work, not a byproduct of Phase 3.

- [ ] Scorer subclasses tested against fixed strings — exercises the hierarchy,
      not just the leaves
- [ ] Model access injected; the model-graded scorer tested against a mock
      client that returns canned verdicts
- [ ] Adapter tests: garbage survives intact, nothing clamped or repaired

**Acceptance:** `uv run pytest` is green with `ANTHROPIC_API_KEY` unset. A test
that needs a key is written wrong (AGENTS §4).

---

## Phase 4 — Grounding scorer (headline metric)

- [ ] Claim extraction from generated copy → atomic claims
- [ ] Verify each claim against the structured input: supported / contradicted /
      unsupported / review-sourced
- [ ] Review-sourced = traceable only to a guest review. Reported as its own
      number, never folded into precision. An owner republishing a guest's
      opinion as a first-party marketing claim is a distinct risk, and averaging
      it away is the exact failure this eval exists to prevent
- [ ] Aggregate precision + recall over the first three categories

**Acceptance:** on a fixture with a planted hallucinated amenity, the scorer
marks that claim unsupported and precision drops. On a fixture whose only
support is a review, the claim lands in the fourth bucket and precision does not
move. Re-run hits Inspect's cache, no second API call.

---

## Phase 5 — Judge calibration (HUMAN WORK)

- [ ] `TODO(human)`: hand-label ~20 generations from the frozen Phase 2 run. Not
      agent-generated (AGENTS §5)
- [ ] That run is `gen_v0`'s deliberately-bad output, and that is correct — you
      are calibrating the judge, not the generator. Obvious hallucinations are
      easier to label and make disagreement more diagnostic. Do not wait for a
      "good" run to label. Label v0 once and never re-label against a later run:
      the labels join by hash of the generation text (AGENTS §6), so re-labelling
      orphans them and silently invalidates every agreement number
- [ ] Judge vs hand labels → agreement (bias)
- [ ] Judge vs itself across repeats → self-consistency (variance)
- [ ] One paragraph: what the judge is and isn't trustworthy for

**Acceptance:** both numbers reported together with a plain statement of what
stays unmeasured.

---

## Phase 6 — Iterate v0 → v1 (→ v2 if time)

- [ ] `gen_v1`: fix the dominant failure v0's scores exposed
- [ ] Results table: metric per version with confidence intervals
- [ ] Paired significance test — did it help, or is it noise?

**Acceptance:** each version names the failure it targets; a change that didn't
help stays in the table, reported honestly. If short on time, v1 only.

---

## Phase 7 — Adversarial + injection report

- [ ] Scores broken out: adversarial slice vs realistic slice
- [ ] Injection cases: does owner text steer the output? State the outcome even
      if it fails
- [ ] Any mitigation, and its cost

**Acceptance:** injection result stated explicitly. A reported vulnerability
beats a silent one.

---

## Phase 8 — Notebook + README

- [ ] `evals.ipynb` runs the pipeline top to bottom and reads the committed logs
- [ ] README: approach, `uv sync` run steps, how to read the logs, how AI was used
- [ ] Notebook narrative: assumptions/scope up top; each metric justified in
      customer terms; trade-offs + roads-not-taken at the end (JSONL-vs-DB is
      moot now — instead: why these metrics, why Inspect, what breaks at scale,
      online signal = owner edit-rate)
- [ ] State plainly: if the generator emits JSON via tool use, the format scorer
      passes by construction. Keep it as a regression guard, but name
      constrained decoding — not prompt quality — as what passes it
- [ ] "What I did not build and why": RAG, fine-tuning, agents, serving, and
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
