"""Inspect scorers built from the deterministic checks.

Thin on purpose. The logic lives in `checks.py`; this module only adapts it to
Inspect's interface, so the check hierarchy stays testable as plain objects and
Inspect keeps owning scoring, metrics, and logging.
"""

from __future__ import annotations

import asyncio
from typing import Protocol

from inspect_ai.model import ModelOutput, get_model
from inspect_ai.scorer import Score, Scorer, Target, accuracy, mean, scorer, stderr
from inspect_ai.solver import TaskState

from lodgify_challenge.checks import ALL_CHECKS, DeterministicCheck
from lodgify_challenge.grounding import (
    Verdict,
    build_claim_prompt,
    build_coverage_prompt,
    build_extraction_prompt,
    parse_claim_verdict,
    parse_claims,
    parse_coverage,
    summarise,
)
from lodgify_challenge.listing import PropertyListing


class Judge(Protocol):
    """What the grounding scorer needs from a model.

    Narrower than Inspect's `Model` on purpose: this is the seam the test suite
    injects through, so the model-graded path runs with no key and no network.

    Annotation only. The runtime check is a plain `hasattr` — making this
    `@runtime_checkable` would permit `isinstance`, but that check verifies only
    that the attribute name exists, not its signature, so it would look like
    stronger validation than it is.
    """

    async def generate(self, input: str, /) -> ModelOutput: ...


def _listing_from(state: TaskState) -> PropertyListing:
    return PropertyListing.model_validate(state.metadata["listing"])


def check_scorer(check: DeterministicCheck) -> Scorer:
    """Adapt one check to an Inspect scorer.

    Score is all-or-nothing: 1.0 clean, 0.0 if anything was found. A fractional
    score would let copy with one hallucinated price claim average out to
    "mostly fine", which is not how the failure behaves for the owner publishing
    it. The individual findings ride in metadata so nothing is lost.
    """

    @scorer(metrics=[accuracy(), stderr()], name=check.name)
    def build() -> Scorer:
        async def score(state: TaskState, target: Target) -> Score:
            findings = check.findings(state.output.completion, _listing_from(state))
            return Score(
                value=0.0 if findings else 1.0,
                answer="clean" if not findings else f"{len(findings)} finding(s)",
                explanation=(
                    check.rationale
                    if not findings
                    else "; ".join(str(f) for f in findings)
                ),
                metadata={
                    "check": check.name,
                    "findings": [
                        {"detail": f.detail, "evidence": f.evidence} for f in findings
                    ],
                },
            )

        return score

    return build()


@scorer(
    metrics={
        "precision": [mean(), stderr()],
        "recall": [mean()],
        "review_sourced_rate": [mean()],
    },
    name="grounding",
)
def grounding(judge: Judge | str | None = None) -> Scorer:
    """Extract atomic claims, then verify each against the structured input.

    Every claim is judged in its own call. That costs roughly twice a batched
    pass and issues about fifteen times the calls, and it buys measurement
    validity: judged together, an early verdict anchors later ones and the model
    drifts toward internal consistency, so the judgements are not independent.
    It also makes a truncated response a one-claim loss rather than losing the
    whole sample.

    Claims within a sample are verified concurrently, so wall-clock scales with
    the slowest claim rather than with their number.

    The judge model is injected so it can be swapped or mocked; tests never reach
    the network.
    """

    async def score(state: TaskState, target: Target) -> Score:
        model = judge if hasattr(judge, "generate") else get_model(judge)
        listing = _listing_from(state)
        copy = state.output.completion

        extraction = await model.generate(build_extraction_prompt(copy))
        claims = parse_claims(extraction.completion)

        if not claims:
            return Score(
                value={"precision": 1.0, "recall": 0.0, "review_sourced_rate": 0.0},
                answer="no claims extracted",
                explanation="No factual claims found. Perfectly grounded and useless — "
                "which is why recall is reported beside precision.",
                metadata={"claims": [], "judgements": []},
            )

        responses = await asyncio.gather(
            *(model.generate(build_claim_prompt(listing, c)) for c in claims),
            model.generate(build_coverage_prompt(listing, copy)),
        )
        judgements = [
            parse_claim_verdict(r.completion, c) for r, c in zip(responses[:-1], claims)
        ]
        covered = parse_coverage(responses[-1].completion)
        result = summarise(listing, judgements, covered)

        return Score(
            value={
                "precision": result.precision,
                "recall": result.recall,
                "review_sourced_rate": result.review_sourced_rate,
            },
            answer=(
                f"{result.count(Verdict.SUPPORTED)} supported, "
                f"{result.count(Verdict.CONTRADICTED)} contradicted, "
                f"{result.count(Verdict.UNSUPPORTED)} unsupported, "
                f"{result.count(Verdict.REVIEW_SOURCED)} review-sourced"
            ),
            explanation="; ".join(
                f"[{j.verdict}] {j.claim}"
                for j in judgements
                if j.verdict is not Verdict.SUPPORTED
            )
            or "every claim traced to the structured input",
            metadata={
                "judgements": [
                    {"claim": j.claim, "verdict": str(j.verdict), "evidence": j.evidence}
                    for j in judgements
                ],
                "facts_total": result.facts_total,
                "facts_covered": result.facts_covered,
            },
        )

    return score


def deterministic_scorers() -> list[Scorer]:
    """Every deterministic check, in a fixed order.

    These run before any model-graded scorer (AGENTS §4) — they need no API call
    and catch the obvious for free.
    """
    return [check_scorer(cls()) for cls in ALL_CHECKS]
