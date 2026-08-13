"""Tests for the Inspect adapter around the deterministic checks.

The check logic is tested in `test_checks.py`; this file only covers the bridge:
score convention, findings surviving into metadata, and one scorer per check.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from lodgify_challenge.checks import ALL_CHECKS, PlaceholderLeakage, RequiredSections
from lodgify_challenge.scorers import check_scorer, deterministic_scorers
from _helpers import CLEAN, listing


@dataclass
class FakeOutput:
    completion: str


@dataclass
class FakeState:
    """Duck-typed stand-in for TaskState.

    A real TaskState needs a model and a full sample; the adapter only reads the
    completion and the metadata, so a stub keeps these tests offline and fast.
    """

    completion: str
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def output(self) -> FakeOutput:
        return FakeOutput(self.completion)


def run_scorer(check_cls: type, text: str) -> Any:
    scorer_fn = check_scorer(check_cls())
    state = FakeState(text, {"listing": listing().model_dump()})
    return asyncio.run(scorer_fn(state, None))


def test_clean_copy_scores_one() -> None:
    score = run_scorer(RequiredSections, CLEAN)
    assert score.value == 1.0
    assert score.answer == "clean"


def test_a_single_finding_drops_the_score_to_zero() -> None:
    """All-or-nothing on purpose: one hallucinated price claim should not average
    away into 'mostly fine'."""
    score = run_scorer(PlaceholderLeakage, "## HERO HEADLINE\n{{name}}\n")
    assert score.value == 0.0


def test_findings_survive_into_metadata_for_later_analysis() -> None:
    score = run_scorer(PlaceholderLeakage, "## HERO HEADLINE\n{{name}}\n")
    findings = score.metadata["findings"]
    assert findings[0]["evidence"] == "{{name}}"
    assert score.metadata["check"] == "placeholder_leakage"


def test_explanation_carries_the_rationale_when_clean() -> None:
    score = run_scorer(RequiredSections, CLEAN)
    assert "publishable" in score.explanation


def test_explanation_lists_the_findings_when_not_clean() -> None:
    score = run_scorer(RequiredSections, "## HIGHLIGHTS\nx\n")
    assert "missing section HERO HEADLINE" in score.explanation


def test_one_scorer_is_built_per_check() -> None:
    assert len(deterministic_scorers()) == len(ALL_CHECKS)
