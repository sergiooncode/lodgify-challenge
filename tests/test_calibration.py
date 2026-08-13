"""Calibration arithmetic against fixed inputs — no network, no judge."""

from __future__ import annotations

import json
from pathlib import Path

from lodgify_challenge.analysis.calibration import (
    TODO,
    Agreement,
    LabelRecord,
    compare,
    generation_hash,
    load_labels,
    self_consistency,
)
from lodgify_challenge.eval.grounding import Verdict

S, C, U, R = (
    Verdict.SUPPORTED,
    Verdict.CONTRADICTED,
    Verdict.UNSUPPORTED,
    Verdict.REVIEW_SOURCED,
)


def agreement(*pairs: tuple[Verdict, Verdict]) -> Agreement:
    return Agreement(pairs=list(pairs))


# --- hashing -----------------------------------------------------------------


def test_generation_hash_is_stable_and_content_addressed() -> None:
    assert generation_hash("copy") == generation_hash("copy")
    assert generation_hash("copy") != generation_hash("copy ")


# --- label loading -----------------------------------------------------------


def test_unlabelled_rows_are_skipped_not_counted() -> None:
    """A TODO row is not a label. Counting it would silently corrupt agreement."""
    line = json.dumps({"generation_sha256": "a", "claim": "x", "verdict": TODO})
    assert LabelRecord.parse(line) is None


def test_blank_and_comment_lines_are_skipped() -> None:
    assert LabelRecord.parse("") is None
    assert LabelRecord.parse("  ") is None
    assert LabelRecord.parse("# a note") is None


def test_a_labelled_row_parses() -> None:
    line = json.dumps(
        {"generation_sha256": "abc", "claim": "four bedrooms",
         "verdict": "supported", "note": "rental_info"}
    )
    record = LabelRecord.parse(line)
    assert record is not None
    assert record.verdict is S
    assert record.note == "rental_info"


def test_loading_a_missing_file_is_empty_not_an_error() -> None:
    assert load_labels(Path("/nonexistent/labels.jsonl")) == []


def test_loading_reads_only_labelled_rows(tmp_path: Path) -> None:
    path = tmp_path / "labels.jsonl"
    path.write_text(
        json.dumps({"generation_sha256": "a", "claim": "x", "verdict": "supported"})
        + "\n"
        + json.dumps({"generation_sha256": "a", "claim": "y", "verdict": TODO})
        + "\n"
    )
    assert [r.claim for r in load_labels(path)] == ["x"]


# --- agreement ---------------------------------------------------------------


def test_perfect_agreement() -> None:
    a = agreement((S, S), (U, U), (R, R))
    assert a.raw == 1.0
    assert a.kappa == 1.0


def test_total_disagreement() -> None:
    a = agreement((S, U), (U, S))
    assert a.raw == 0.0
    assert a.kappa < 0


def test_kappa_punishes_a_judge_that_always_says_the_same_thing() -> None:
    """Raw agreement flatters a constant judge on a skewed distribution; kappa is
    what stops that reading as skill."""
    a = agreement((S, S), (S, S), (S, S), (U, S))
    assert a.raw == 0.75
    assert a.kappa < a.raw


def test_kappa_is_zero_when_chance_agreement_is_degenerate() -> None:
    a = agreement((S, S), (S, S))
    assert a.kappa == 0.0


def test_empty_agreement_is_zero_not_a_crash() -> None:
    a = agreement()
    assert a.raw == 0.0 and a.kappa == 0.0 and a.n == 0


def test_disagreements_are_listed_for_inspection() -> None:
    a = agreement((S, S), (R, S))
    assert a.disagreements() == [(R, S)]


def test_confusion_counts_every_pairing() -> None:
    a = agreement((S, S), (S, S), (R, S))
    assert a.confusion()[(S, S)] == 2
    assert a.confusion()[(R, S)] == 1


# --- matching ----------------------------------------------------------------


def test_labels_match_judge_verdicts_by_hash_and_claim() -> None:
    labels = [LabelRecord("h1", "a villa", S)]
    judged = {("h1", "a villa"): U}
    a = compare(labels, judged)
    assert a.pairs == [(S, U)]
    assert a.unmatched_labels == 0


def test_a_label_whose_generation_changed_is_reported_not_dropped() -> None:
    """The loud failure the hash join exists to produce: re-generating orphans
    every label, and silence would look like having no disagreements."""
    labels = [LabelRecord("old-hash", "a villa", S)]
    a = compare(labels, {("new-hash", "a villa"): S})
    assert a.n == 0
    assert a.unmatched_labels == 1


def test_only_labelled_claims_are_compared() -> None:
    labels = [LabelRecord("h", "a", S)]
    judged = {("h", "a"): S, ("h", "b"): U}
    assert compare(labels, judged).n == 1


# --- self-consistency --------------------------------------------------------


def test_a_stable_judge_scores_one() -> None:
    sc = self_consistency([{"a": S, "b": U}, {"a": S, "b": U}, {"a": S, "b": U}])
    assert sc.stable_share == 1.0
    assert sc.repeats == 3
    assert sc.unstable() == {}


def test_an_unstable_claim_is_surfaced() -> None:
    sc = self_consistency([{"a": S, "b": U}, {"a": R, "b": U}])
    assert sc.stable_share == 0.5
    assert list(sc.unstable()) == ["a"]


def test_only_claims_present_in_every_pass_are_counted() -> None:
    """Extraction instability is a different failure from verdict instability;
    blending them would hide both."""
    sc = self_consistency([{"a": S, "b": S}, {"a": S}])
    assert sc.n == 1


def test_no_passes_is_zero_not_a_crash() -> None:
    sc = self_consistency([])
    assert sc.n == 0 and sc.stable_share == 0.0 and sc.repeats == 0
