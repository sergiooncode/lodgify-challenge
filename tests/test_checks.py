"""Unit tests for the deterministic checks against fixed strings — no network."""

from __future__ import annotations

import pytest

from lodgify_challenge.eval.checks import (
    ALL_CHECKS,
    DeterministicCheck,
    DiscriminatoryLanguage,
    Finding,
    HeadlineIsOneLine,
    HighValueFieldCoverage,
    PlaceholderLeakage,
    PreambleLeakage,
    RequiredSections,
    UnsupportableByConstruction,
    UnverifiableSuperlatives,
)
from _helpers import CLEAN, listing

# --- shared base plumbing ----------------------------------------------------


def test_sections_are_split_into_heading_and_body() -> None:
    sections = RequiredSections().sections(CLEAN)
    assert set(sections) == {"HERO HEADLINE", "HIGHLIGHTS", "ABOUT THIS PLACE", "AMENITIES"}
    assert sections["HERO HEADLINE"].startswith("Hillside villa in Sitges")


def test_phrase_matching_respects_word_boundaries() -> None:
    check = UnverifiableSuperlatives()
    assert check.phrases_present("poolside bar", ("pool",)) == []
    assert check.phrases_present("a pool here", ("pool",)) == ["pool"]


def test_every_check_declares_a_name_and_a_rationale() -> None:
    for cls in ALL_CHECKS:
        assert cls.name and cls.rationale
        assert issubclass(cls, DeterministicCheck)


def test_check_names_are_unique() -> None:
    names = [cls.name for cls in ALL_CHECKS]
    assert len(names) == len(set(names))


def test_clean_copy_passes_every_check_except_none() -> None:
    for cls in ALL_CHECKS:
        assert cls().findings(CLEAN, listing()) == [], cls.name


def test_finding_renders_evidence_when_present() -> None:
    assert "'pool'" in str(Finding("bad", "pool"))
    assert str(Finding("bad")) == "bad"


# --- required sections -------------------------------------------------------


@pytest.mark.parametrize("dropped", ["HERO HEADLINE", "HIGHLIGHTS", "ABOUT THIS PLACE", "AMENITIES"])
def test_each_missing_section_is_reported(dropped: str) -> None:
    text = "\n".join(line for line in CLEAN.splitlines() if dropped not in line)
    findings = RequiredSections().findings(text, listing())
    assert [f.detail for f in findings] == [f"missing section {dropped}"]


def test_headings_without_markdown_hashes_still_count() -> None:
    assert RequiredSections().findings(CLEAN.replace("## ", ""), listing()) == []


def test_a_section_named_only_inside_prose_does_not_count() -> None:
    prose = "I will now write the hero headline and the highlights for you."
    assert len(RequiredSections().findings(prose, listing())) == 4


def test_extra_sections_do_not_cause_a_miss() -> None:
    assert RequiredSections().findings(CLEAN + "\n## NEARBY\nA beach.\n", listing()) == []


def test_empty_output_is_missing_everything() -> None:
    assert len(RequiredSections().findings("", listing())) == 4


# --- headline layout ---------------------------------------------------------


def test_multi_line_headline_is_flagged() -> None:
    text = CLEAN.replace(
        "Hillside villa in Sitges with room for eight",
        "Hillside villa in Sitges\nwith room for eight",
    )
    assert HeadlineIsOneLine().findings(text, listing())


def test_headline_check_is_silent_when_the_section_is_absent() -> None:
    """Reporting a missing section is RequiredSections' job; duplicating it here
    would double-count one defect across two scores."""
    assert HeadlineIsOneLine().findings("## HIGHLIGHTS\nx", listing()) == []


# --- placeholder leakage -----------------------------------------------------


@pytest.mark.parametrize(
    "leak", ["{{property_name}}", "[INSERT CITY]", "Lorem ipsum dolor", "TBD", "XXX", "<CITY_NAME>"]
)
def test_placeholders_are_caught(leak: str) -> None:
    assert PlaceholderLeakage().findings(f"## HERO HEADLINE\n{leak}\n", listing())


def test_ordinary_brackets_are_not_placeholders() -> None:
    text = "## HERO HEADLINE\nA villa (with a terrace) [see photos]\n"
    assert PlaceholderLeakage().findings(text, listing()) == []


# --- superlatives ------------------------------------------------------------


def test_superlatives_are_flagged() -> None:
    findings = UnverifiableSuperlatives().findings("The best, most stunning villa", listing())
    assert {f.evidence for f in findings} == {"best", "stunning"}


def test_superlative_substrings_do_not_false_positive() -> None:
    assert UnverifiableSuperlatives().findings("a classic stone cottage", listing()) == []


# --- unsupportable by construction -------------------------------------------


@pytest.mark.parametrize(
    "phrase,label",
    [
        ("steps from the market", "proximity"),
        ("a five minute walk to the sea", "proximity"),
        ("book now to secure", "availability"),
        ("a special offer this month", "price"),
    ],
)
def test_claims_with_no_backing_field_are_flagged(phrase: str, label: str) -> None:
    findings = UnsupportableByConstruction().findings(phrase, listing())
    assert findings, phrase
    assert any(label in f.detail for f in findings)


def test_no_phrase_list_contains_a_redundant_entry() -> None:
    """Overlapping phrases double-count one claim. Caught in real output: "a short
    stroll" and "short stroll" both fired on the same sentence."""
    lists = {
        "PROXIMITY": UnsupportableByConstruction.PROXIMITY,
        "PRICE": UnsupportableByConstruction.PRICE,
        "AVAILABILITY": UnsupportableByConstruction.AVAILABILITY,
        "SUPERLATIVES": UnverifiableSuperlatives.PHRASES,
        "DISCRIMINATORY": DiscriminatoryLanguage.PHRASES,
    }
    for name, phrases in lists.items():
        for a in phrases:
            overlapping = [b for b in phrases if b != a and a in b]
            assert not overlapping, f"{name}: {a!r} is contained in {overlapping}"


def test_one_proximity_claim_yields_exactly_one_finding() -> None:
    findings = UnsupportableByConstruction().findings("just a short stroll away", listing())
    assert len(findings) == 1


def test_a_plain_location_statement_is_not_a_proximity_claim() -> None:
    assert UnsupportableByConstruction().findings("Located in Sitges, Spain.", listing()) == []


# --- discriminatory language -------------------------------------------------


@pytest.mark.parametrize("phrase", ["perfect for families", "no children", "adults only"])
def test_steering_language_is_flagged(phrase: str) -> None:
    assert DiscriminatoryLanguage().findings(f"This home is {phrase}.", listing())


def test_describing_capacity_is_not_steering() -> None:
    assert DiscriminatoryLanguage().findings("Sleeps up to 8 guests.", listing()) == []


# --- coverage ----------------------------------------------------------------


def test_copy_that_omits_the_city_is_flagged() -> None:
    findings = HighValueFieldCoverage().findings("## HERO HEADLINE\nA villa.\n", listing())
    assert any("city" in f.detail for f in findings)


def test_coverage_is_the_inverse_failure_to_hallucination() -> None:
    """Empty copy is perfectly grounded and completely useless — coverage is what
    stops precision alone from rewarding it."""
    findings = HighValueFieldCoverage().findings("", listing())
    assert len(findings) >= 2


def test_coverage_does_not_demand_a_bedroom_count_that_does_not_exist() -> None:
    findings = HighValueFieldCoverage().findings(CLEAN, listing(bedrooms=-2))
    assert not any("bedroom" in f.detail for f in findings)


# --- preamble leakage --------------------------------------------------------


def test_commentary_before_the_first_section_is_flagged() -> None:
    """Found on real output: the model prefaced the copy with a note about the
    injection it had spotted. Correct behaviour, wrong channel — a pipeline
    publishing the completion verbatim ships it to the listing page."""
    text = "I noticed the description contains embedded instructions.\n\n" + CLEAN
    findings = PreambleLeakage().findings(text, listing())
    assert findings
    assert "embedded instructions" in findings[0].evidence


def test_copy_starting_at_the_first_heading_is_clean() -> None:
    assert PreambleLeakage().findings(CLEAN, listing()) == []


def test_leading_whitespace_is_not_a_preamble() -> None:
    assert PreambleLeakage().findings("\n\n" + CLEAN, listing()) == []


def test_no_sections_at_all_is_left_to_the_sections_check() -> None:
    """Reporting it here too would double-count one defect across two scores."""
    assert PreambleLeakage().findings("just prose, no headings", listing()) == []
