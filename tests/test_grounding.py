"""Grounding logic against fixed strings — no network, no judge."""

from __future__ import annotations

import json

import pytest

from _helpers import listing
from lodgify_challenge.eval.grounding import (
    Judgement,
    Verdict,
    build_claim_prompt,
    build_coverage_prompt,
    key_facts,
    parse_claims,
    parse_claim_verdict,
    parse_coverage,
    summarise,
)


def judged(*pairs: tuple[str, Verdict]) -> list[Judgement]:
    return [Judgement(c, v) for c, v in pairs]


def result(*pairs: tuple[str, Verdict], covered: set[int] | None = None):
    return summarise(listing(), judged(*pairs), covered or set())


# --- verdict parsing ---------------------------------------------------------


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("supported", Verdict.SUPPORTED),
        ("  CONTRADICTED ", Verdict.CONTRADICTED),
        ("review_sourced", Verdict.REVIEW_SOURCED),
        ("nonsense", Verdict.UNSUPPORTED),
        ("", Verdict.UNSUPPORTED),
    ],
)
def test_verdicts_parse_leniently_and_fail_closed(raw: str, expected: Verdict) -> None:
    assert Verdict.parse(raw) is expected


# --- precision: the review-sourced rule --------------------------------------


def test_review_sourced_claims_are_excluded_from_precision_entirely() -> None:
    """The rule the whole design turns on: a review-sourced claim may not move
    precision up or down."""
    without = result(("a", Verdict.SUPPORTED), ("b", Verdict.UNSUPPORTED))
    with_review = result(
        ("a", Verdict.SUPPORTED),
        ("b", Verdict.UNSUPPORTED),
        ("c", Verdict.REVIEW_SOURCED),
    )
    assert with_review.precision == without.precision == 0.5


def test_review_sourced_claims_are_reported_on_their_own() -> None:
    res = result(("a", Verdict.SUPPORTED), ("c", Verdict.REVIEW_SOURCED))
    assert res.review_sourced_rate == 0.5
    assert res.precision == 1.0


def test_copy_made_entirely_of_review_claims_has_a_visible_rate() -> None:
    res = result(("a", Verdict.REVIEW_SOURCED), ("b", Verdict.REVIEW_SOURCED))
    assert res.review_sourced_rate == 1.0
    assert res.precision == 1.0, "no first-party claims to be wrong about"


def test_contradicted_and_unsupported_both_cost_precision() -> None:
    assert result(("a", Verdict.SUPPORTED), ("b", Verdict.CONTRADICTED)).precision == 0.5
    assert result(("a", Verdict.SUPPORTED), ("b", Verdict.UNSUPPORTED)).precision == 0.5


def test_a_planted_hallucination_drops_precision() -> None:
    clean = result(("a", Verdict.SUPPORTED), ("b", Verdict.SUPPORTED))
    planted = result(
        ("a", Verdict.SUPPORTED),
        ("b", Verdict.SUPPORTED),
        ("heated private pool", Verdict.UNSUPPORTED),
    )
    assert clean.precision == 1.0
    assert planted.precision < clean.precision


# --- recall ------------------------------------------------------------------


def test_recall_counts_covered_key_facts() -> None:
    res = result(("a", Verdict.SUPPORTED), covered={0, 1})
    assert res.facts_covered == 2
    assert res.recall == pytest.approx(2 / res.facts_total)


def test_out_of_range_fact_indices_are_ignored() -> None:
    res = result(("a", Verdict.SUPPORTED), covered={0, 999, -3})
    assert res.facts_covered == 1


def test_empty_copy_is_perfectly_precise_and_has_no_recall() -> None:
    """The failure precision alone cannot see."""
    res = summarise(listing(), [], set())
    assert res.precision == 1.0
    assert res.recall == 0.0


# --- parsing -----------------------------------------------------------------


def test_claims_parse_from_a_fenced_json_block() -> None:
    raw = '```json\n{"claims": ["a villa", "four bedrooms"]}\n```'
    assert parse_claims(raw) == ["a villa", "four bedrooms"]


def test_claims_parse_when_prose_surrounds_the_json() -> None:
    raw = 'Here you go:\n{"claims": ["a villa"]}\nHope that helps.'
    assert parse_claims(raw) == ["a villa"]


def test_unparseable_extraction_yields_no_claims() -> None:
    assert parse_claims("I could not do that") == []


def test_blank_claims_are_dropped() -> None:
    assert parse_claims('{"claims": ["a", "  ", ""]}') == ["a"]


def test_a_single_claim_verdict_parses() -> None:
    raw = '{"verdict": "supported", "evidence": "rental_info.bedrooms = 4"}'
    judgement = parse_claim_verdict(raw, "four bedrooms")
    assert judgement.verdict is Verdict.SUPPORTED
    assert judgement.claim == "four bedrooms"
    assert "bedrooms" in judgement.evidence


def test_a_verdict_wrapped_in_a_code_fence_parses() -> None:
    raw = '```json\n{"verdict": "contradicted"}\n```'
    assert parse_claim_verdict(raw, "sleeps 40").verdict is Verdict.CONTRADICTED


def test_an_unreadable_verdict_fails_closed() -> None:
    """One claim lost, not the whole sample — the reason per-claim verification
    is more robust than judging everything in one response."""
    judgement = parse_claim_verdict("I cannot answer that", "a pool")
    assert judgement.verdict is Verdict.UNSUPPORTED
    assert "no verdict" in judgement.evidence


def test_a_truncated_verdict_fails_closed() -> None:
    assert parse_claim_verdict('{"verdict": "suppo', "a pool").verdict is Verdict.UNSUPPORTED


def test_coverage_indices_parse() -> None:
    assert parse_coverage('{"facts_covered": [0, 2, 5]}') == {0, 2, 5}


def test_unreadable_coverage_yields_nothing_covered() -> None:
    assert parse_coverage("no idea") == set()


def test_non_numeric_coverage_entries_are_ignored() -> None:
    assert parse_coverage('{"facts_covered": [0, "two", null]}') == {0}


# --- prompt construction -----------------------------------------------------


def test_claim_prompt_separates_reviews_from_structured_data() -> None:
    """If reviews leaked into the structured section the judge could not tell
    review-sourced from supported, and the fourth verdict would be unreachable."""
    with_review = listing(reviews=["The beach is a five minute walk."], review_count=1)
    prompt = build_claim_prompt(with_review, "the beach is close")
    structured, reviews = prompt.split("GUEST REVIEWS")
    assert "five minute walk" not in structured
    assert "five minute walk" in reviews


def test_claim_prompt_states_the_review_rule_explicitly() -> None:
    prompt = build_claim_prompt(listing(), "a villa")
    assert "never mark such a claim" in prompt.lower()


def test_claim_prompt_carries_the_claim_under_test() -> None:
    assert "CLAIM:\na heated private pool" in build_claim_prompt(listing(), "a heated private pool")


def test_coverage_prompt_numbers_the_key_facts_and_includes_the_copy() -> None:
    prompt = build_coverage_prompt(listing(), "## HERO HEADLINE\nA villa.")
    assert "0. located in Sitges, Spain" in prompt
    assert "A villa." in prompt


def test_key_facts_come_only_from_structured_fields() -> None:
    facts = key_facts(listing(reviews=["A guest said the beach is close."]))
    assert not any("beach" in f for f in facts)
    assert any("Sitges" in f for f in facts)
