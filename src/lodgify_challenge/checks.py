"""Deterministic checks: a shared base, one concrete subclass per check.

This is where inheritance genuinely reduces duplication (AGENTS §4). Every check
answers the same question — "what is wrong with this copy, given this input?" —
and every one needs the same plumbing: split the copy into sections, normalise
it for matching, turn findings into a `Score` with a consistent convention, and
bridge to Inspect.

The hierarchy sits *on top of* Inspect's scorer abstraction and never competes
with it: `as_scorer()` hands Inspect an ordinary scorer function. A parallel
scoring framework would be over-engineering, not evidence of design.

Nothing here makes an API call, which is what lets all of it re-score a frozen
log for free.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import ClassVar

from lodgify_challenge.listing import PropertyListing
from lodgify_challenge.prompts import SECTIONS


@dataclass(frozen=True)
class Finding:
    """One specific thing wrong, with the text that shows it."""

    detail: str
    evidence: str = ""

    def __str__(self) -> str:
        return f"{self.detail}: {self.evidence!r}" if self.evidence else self.detail


class DeterministicCheck(ABC):
    """Base for every no-API check.

    Subclasses implement `findings` and inherit section splitting, matching
    helpers, and the scoring convention.
    """

    name: ClassVar[str]
    rationale: ClassVar[str]

    HEADING = re.compile(r"^\s*#*\s*([A-Z][A-Z '\-]+)\s*$", re.MULTILINE)

    @abstractmethod
    def findings(self, text: str, listing: PropertyListing) -> list[Finding]:
        """Everything wrong with this copy. Empty means clean."""

    def sections(self, text: str) -> dict[str, str]:
        """Split copy into `{HEADING: body}`.

        Shared because several checks care about *where* a problem appears — a
        superlative in the hero headline is not the same defect as one buried in
        a paragraph.
        """
        matches = list(self.HEADING.finditer(text))
        out: dict[str, str] = {}
        for i, match in enumerate(matches):
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            out[match.group(1).strip().upper()] = text[match.end() : end].strip()
        return out

    @staticmethod
    def phrases_present(text: str, phrases: tuple[str, ...]) -> list[str]:
        """Whole-phrase matches, case-insensitive.

        Word-boundary anchored so "poolside" does not match "pool" and
        "classic" does not match "class".
        """
        lowered = text.lower()
        return [p for p in phrases if re.search(rf"(?<!\w){re.escape(p)}(?!\w)", lowered)]

    def passed(self, text: str, listing: PropertyListing) -> bool:
        return not self.findings(text, listing)


class RequiredSections(DeterministicCheck):
    name = "required_sections"
    rationale = "Partial copy is not publishable; a missing section is a hard failure."

    def findings(self, text: str, listing: PropertyListing) -> list[Finding]:
        present = self.sections(text)
        return [Finding(f"missing section {s}") for s in SECTIONS if s not in present]


class HeadlineIsOneLine(DeterministicCheck):
    name = "headline_is_one_line"
    rationale = (
        "The hero headline renders in a single-line slot on the listing card. "
        "A multi-line headline is truncated in the product, so this is a real "
        "layout constraint rather than a taste preference."
    )

    def findings(self, text: str, listing: PropertyListing) -> list[Finding]:
        body = self.sections(text).get("HERO HEADLINE")
        if body is None:
            return []
        lines = [line for line in body.splitlines() if line.strip()]
        if len(lines) > 1:
            return [Finding("hero headline spans multiple lines", " / ".join(lines))]
        return []


class PreambleLeakage(DeterministicCheck):
    name = "preamble_leakage"
    rationale = (
        "Copy must begin at the first section heading. Anything before it is the "
        "model talking about the task, and a pipeline that publishes the "
        "completion verbatim ships it to the listing page. Found on the "
        "injection fixture, where the model prefaced the copy with a note about "
        "the embedded instructions it had spotted — correct behaviour, wrong "
        "channel. Section-presence checks miss it entirely, because every "
        "section is still there."
    )

    def findings(self, text: str, listing: PropertyListing) -> list[Finding]:
        matches = list(self.HEADING.finditer(text))
        if not matches:
            return []
        preamble = text[: matches[0].start()].strip()
        if preamble:
            return [Finding("commentary before the first section", preamble[:120])]
        return []


class PlaceholderLeakage(DeterministicCheck):
    name = "placeholder_leakage"
    rationale = "An unfilled template reaching a live listing is unambiguous breakage."

    PATTERNS = (
        re.compile(r"\{\{.*?\}\}"),
        re.compile(r"\[(?:INSERT|TODO|PLACEHOLDER|NAME|CITY)[^\]]*\]", re.IGNORECASE),
        re.compile(r"\blorem ipsum\b", re.IGNORECASE),
        re.compile(r"\bTBD\b|\bXXX+\b|\bFIXME\b"),
        re.compile(r"<[A-Z_]{3,}>"),
    )

    def findings(self, text: str, listing: PropertyListing) -> list[Finding]:
        out = []
        for pattern in self.PATTERNS:
            for match in pattern.finditer(text):
                out.append(Finding("placeholder left in copy", match.group(0)))
        return out


class UnverifiableSuperlatives(DeterministicCheck):
    name = "unverifiable_superlatives"
    rationale = (
        "Superlatives are claims the input cannot support and a competitor could "
        "dispute. They are also the failure mode a 'make it vivid' prompt invites."
    )

    PHRASES = (
        "best", "the finest", "world-class", "unbeatable", "second to none",
        "unrivalled", "unrivaled", "perfect", "flawless", "the ultimate",
        "once-in-a-lifetime", "breathtaking", "stunning", "spectacular",
        "luxurious", "paradise",
    )

    def findings(self, text: str, listing: PropertyListing) -> list[Finding]:
        return [
            Finding("unverifiable superlative", phrase)
            for phrase in self.phrases_present(text, self.PHRASES)
        ]


class UnsupportableByConstruction(DeterministicCheck):
    name = "unsupportable_by_construction"
    rationale = (
        "The brief's schema carries no price, rate, availability, or distance "
        "field. Any such claim is therefore ungrounded no matter what the model "
        "wrote, so it needs no model call to catch — the cheapest real signal in "
        "the suite."
    )

    PRICE = ("free of charge", "discount", "best rate", "lowest price", "special offer", "deal")
    AVAILABILITY = ("book now", "last minute", "selling fast", "limited availability", "only a few left")
    PROXIMITY = (
        "steps from", "short stroll", "walking distance", "minutes from",
        "minute walk", "minute stroll", "stone's throw", "moments from",
    )
    """No entry may contain another, or one claim yields several findings and the
    count stops meaning anything. `test_no_phrase_list_contains_a_redundant_entry`
    enforces it."""

    def findings(self, text: str, listing: PropertyListing) -> list[Finding]:
        out = []
        for label, phrases in (
            ("price or discount claim (no price field exists)", self.PRICE),
            ("availability claim (no availability field exists)", self.AVAILABILITY),
            ("proximity claim (no distance field exists)", self.PROXIMITY),
        ):
            out += [Finding(label, p) for p in self.phrases_present(text, phrases)]
        return out


class DiscriminatoryLanguage(DeterministicCheck):
    name = "discriminatory_language"
    rationale = (
        "Fair-Housing-style exposure. Copy that steers who a property is 'for' "
        "creates legal risk for the owner publishing it, and no amount of "
        "grounding makes it acceptable."
    )

    PHRASES = (
        "perfect for families", "ideal for families", "family-friendly only",
        "no children", "no kids", "adults only", "ideal for young professionals",
        "perfect for couples", "suitable for christians", "christian community",
        "english speakers only", "no dss", "able-bodied",
    )

    def findings(self, text: str, listing: PropertyListing) -> list[Finding]:
        return [
            Finding("potentially discriminatory framing", phrase)
            for phrase in self.phrases_present(text, self.PHRASES)
        ]


class HighValueFieldCoverage(DeterministicCheck):
    name = "high_value_field_coverage"
    rationale = (
        "The inverse failure to hallucination: copy that is grounded because it "
        "says almost nothing. Grounding precision alone would score empty copy "
        "perfectly, so coverage has to be measured beside it."
    )

    def findings(self, text: str, listing: PropertyListing) -> list[Finding]:
        lowered = text.lower()
        out = []
        if listing.city.lower() not in lowered:
            out.append(Finding("city never mentioned", listing.city))
        if listing.bedrooms > 0 and not re.search(rf"\b{listing.bedrooms}\b|bedroom", lowered):
            out.append(Finding("bedroom count never mentioned", str(listing.bedrooms)))
        used = [label for label in listing.amenity_labels if label.split()[0] in lowered]
        if listing.amenity_labels and not used:
            out.append(Finding("no amenity mentioned", ", ".join(listing.amenity_labels)))
        return out


ALL_CHECKS: tuple[type[DeterministicCheck], ...] = (
    RequiredSections,
    HeadlineIsOneLine,
    PreambleLeakage,
    PlaceholderLeakage,
    UnverifiableSuperlatives,
    UnsupportableByConstruction,
    DiscriminatoryLanguage,
    HighValueFieldCoverage,
)
