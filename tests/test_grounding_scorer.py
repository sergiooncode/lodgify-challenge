"""The model-graded scorer, end to end, with the judge mocked.

This is the path that would otherwise need an API key. The `Judge` protocol is
the seam: a stub returning canned responses exercises extraction, per-claim
verification, coverage, and the metric arithmetic without touching the network.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from typing import Any

from _helpers import listing
from lodgify_challenge.eval.grounding import Verdict
from lodgify_challenge.eval.scorers import grounding


@dataclass
class StubOutput:
    completion: str


@dataclass
class StubJudge:
    """Replies based on which prompt it is given.

    Keyed on prompt content rather than call order, so a change to concurrency
    or call sequence does not silently rewire which answer goes where.
    """

    claims: list[str]
    verdicts: dict[str, str]
    covered: list[int] = field(default_factory=list)
    prompts: list[str] = field(default_factory=list)

    async def generate(self, input: str, /) -> StubOutput:
        self.prompts.append(input)
        if input.startswith("Extract every factual claim"):
            return StubOutput(json.dumps({"claims": self.claims}))
        if input.startswith("Which of these key facts"):
            return StubOutput(json.dumps({"facts_covered": self.covered}))
        claim = input.split("CLAIM:\n", 1)[1].strip()
        return StubOutput(json.dumps({"verdict": self.verdicts[claim], "evidence": "stub"}))


@dataclass
class StubState:
    completion: str
    metadata: dict[str, Any]

    @property
    def output(self) -> StubOutput:
        return StubOutput(self.completion)


def run(judge: StubJudge, copy: str = "## HERO HEADLINE\nA villa.\n"):
    state = StubState(copy, {"listing": listing().model_dump()})
    return asyncio.run(grounding(judge)(state, None))


def test_all_supported_gives_full_precision() -> None:
    judge = StubJudge(
        claims=["a villa", "four bedrooms"],
        verdicts={"a villa": "supported", "four bedrooms": "supported"},
    )
    score = run(judge)
    assert score.value["precision"] == 1.0
    assert score.value["review_sourced_rate"] == 0.0


def test_a_planted_hallucination_lowers_precision() -> None:
    judge = StubJudge(
        claims=["four bedrooms", "a heated private pool"],
        verdicts={"four bedrooms": "supported", "a heated private pool": "unsupported"},
    )
    score = run(judge)
    assert score.value["precision"] == 0.5
    assert "heated private pool" in score.explanation


def test_a_review_sourced_claim_leaves_precision_untouched() -> None:
    """The rule the design turns on, exercised through the real scorer."""
    judge = StubJudge(
        claims=["four bedrooms", "the beach is five minutes away"],
        verdicts={
            "four bedrooms": "supported",
            "the beach is five minutes away": "review_sourced",
        },
    )
    score = run(judge)
    assert score.value["precision"] == 1.0
    assert score.value["review_sourced_rate"] == 0.5


def test_each_claim_gets_its_own_call_plus_one_for_coverage() -> None:
    judge = StubJudge(
        claims=["a", "b", "c"],
        verdicts={"a": "supported", "b": "supported", "c": "supported"},
    )
    run(judge)
    assert len(judge.prompts) == 5, "1 extraction + 3 claims + 1 coverage"


def test_coverage_drives_recall() -> None:
    judge = StubJudge(
        claims=["a villa"], verdicts={"a villa": "supported"}, covered=[0, 1, 2]
    )
    score = run(judge)
    assert 0 < score.value["recall"] < 1


def test_copy_with_no_claims_is_precise_but_has_no_recall() -> None:
    judge = StubJudge(claims=[], verdicts={})
    score = run(judge)
    assert score.value["precision"] == 1.0
    assert score.value["recall"] == 0.0
    assert "useless" in score.explanation


def test_judgements_are_recorded_for_later_inspection() -> None:
    judge = StubJudge(
        claims=["a heated private pool"],
        verdicts={"a heated private pool": "unsupported"},
    )
    score = run(judge)
    recorded = score.metadata["judgements"]
    assert recorded[0]["verdict"] == Verdict.UNSUPPORTED
    assert recorded[0]["claim"] == "a heated private pool"


def test_the_answer_summarises_every_verdict_class() -> None:
    judge = StubJudge(
        claims=["a", "b", "c", "d"],
        verdicts={
            "a": "supported",
            "b": "contradicted",
            "c": "unsupported",
            "d": "review_sourced",
        },
    )
    answer = run(judge).answer
    for label in ("supported", "contradicted", "unsupported", "review-sourced"):
        assert label in answer
