"""The headline metric: are the claims in generated copy traceable to the input?

Everything here is pure — prompt construction, response parsing, metric
arithmetic. The two model calls live in `scorers.py`, so all of this is tested
offline against fixed strings and the judge can be mocked wholesale.

The four verdicts are the point of the design. Folding `review_sourced` into
`supported` would hide the risk this eval exists to surface: an owner
republishing a guest's opinion as a first-party marketing claim is a different
failure from inventing one, and averaging them together makes both invisible.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from enum import StrEnum

from lodgify_challenge.domain.listing import PropertyListing


class Verdict(StrEnum):
    SUPPORTED = "supported"
    CONTRADICTED = "contradicted"
    UNSUPPORTED = "unsupported"
    REVIEW_SOURCED = "review_sourced"

    @classmethod
    def parse(cls, raw: str) -> Verdict:
        """Unknown verdicts become `unsupported` rather than raising.

        A judge that returns something unexpected is a judge failure, and the
        conservative reading of an unreadable verdict is that the claim was not
        shown to be grounded.
        """
        try:
            return cls(str(raw).strip().lower())
        except ValueError:
            return cls.UNSUPPORTED


@dataclass(frozen=True)
class Judgement:
    claim: str
    verdict: Verdict
    evidence: str = ""


@dataclass(frozen=True)
class GroundingResult:
    judgements: list[Judgement]
    facts_total: int
    facts_covered: int

    def count(self, verdict: Verdict) -> int:
        return sum(1 for j in self.judgements if j.verdict is verdict)

    @property
    def precision(self) -> float:
        """Supported over first-party claims.

        `review_sourced` is excluded from both numerator and denominator: it is
        reported on its own and never allowed to move this number in either
        direction.
        """
        first_party = [
            j for j in self.judgements if j.verdict is not Verdict.REVIEW_SOURCED
        ]
        if not first_party:
            return 1.0
        return self.count(Verdict.SUPPORTED) / len(first_party)

    @property
    def review_sourced_rate(self) -> float:
        if not self.judgements:
            return 0.0
        return self.count(Verdict.REVIEW_SOURCED) / len(self.judgements)

    @property
    def recall(self) -> float:
        """Share of high-value input facts the copy actually used.

        Precision alone rewards saying nothing — empty copy is perfectly
        grounded. Recall is the counterweight, and the two are only meaningful
        read together.
        """
        if not self.facts_total:
            return 1.0
        return self.facts_covered / self.facts_total


def key_facts(listing: PropertyListing) -> list[str]:
    """The facts a listing page is expected to convey.

    Deliberately drawn from structured fields only. Nothing sourced from a
    review is a fact the copy is obliged to carry.
    """
    facts = [
        f"located in {listing.city}, {listing.country}",
        f"sleeps {listing.max_guests}",
        f"{listing.bedrooms} bedrooms",
        f"{listing.bathrooms} bathrooms",
        f"check-in {listing.check_in_time}, check-out {listing.check_out_time}",
    ]
    facts += [f"has {label}" for label in listing.amenity_labels]
    if listing.cancellation_policy:
        facts.append(f"cancellation policy: {listing.cancellation_policy}")
    return facts


EXTRACTION_PROMPT = """Extract every factual claim made about the property in the copy below.

A claim is one atomic assertion a reader would take as fact — a feature, a
count, a location, a policy, a comparison. Split compound sentences into
separate claims. Ignore pure exhortation ("book your escape") that asserts
nothing about the property.

Return JSON only, in this exact shape:
{{"claims": ["...", "..."]}}

COPY:
{copy}
"""

SINGLE_CLAIM_PROMPT = """You are auditing one claim from marketing copy for a vacation rental.

Assign exactly one verdict:

- "supported": the STRUCTURED DATA directly supports it.
- "contradicted": the STRUCTURED DATA directly contradicts it.
- "review_sourced": it is supported ONLY by a guest review, not by the
  structured data. A guest's opinion republished as the owner's own marketing
  claim is a distinct risk, so never mark such a claim "supported".
- "unsupported": nothing in either source establishes it. This includes general
  world knowledge and anything about price, availability, or distance — the data
  has no such fields, so any claim of that kind is unsupported however plausible.

Return JSON only: {{"verdict": "...", "evidence": "..."}}

STRUCTURED DATA:
{facts}

GUEST REVIEWS (never sufficient for "supported"):
{reviews}

CLAIM:
{claim}
"""

COVERAGE_PROMPT = """Which of these key facts about the property does the copy convey?

Return JSON only: {{"facts_covered": [0, 2]}}

KEY FACTS:
{key_facts}

COPY:
{copy}
"""


def build_extraction_prompt(copy: str) -> str:
    return EXTRACTION_PROMPT.format(copy=copy)


def _structured_and_reviews(listing: PropertyListing) -> tuple[str, str]:
    """Split the input the judge sees into structured data and reviews.

    They must stay separate or the `review_sourced` verdict is unreachable: a
    judge that cannot tell which source backs a claim cannot mark it.
    """
    from lodgify_challenge.domain.prompts import render_listing

    facts = render_listing(listing)
    for review in listing.reviews:
        facts = facts.replace(f"Guest review: {review}\n", "").replace(
            f"Guest review: {review}", ""
        )
    reviews = "\n".join(f"- {r}" for r in listing.reviews) or "(none)"
    return facts.strip(), reviews


def build_claim_prompt(listing: PropertyListing, claim: str) -> str:
    facts, reviews = _structured_and_reviews(listing)
    return SINGLE_CLAIM_PROMPT.format(facts=facts, reviews=reviews, claim=claim)


def build_coverage_prompt(listing: PropertyListing, copy: str) -> str:
    numbered = "\n".join(f"{i}. {f}" for i, f in enumerate(key_facts(listing)))
    return COVERAGE_PROMPT.format(key_facts=numbered, copy=copy)


def parse_claim_verdict(raw: str, claim: str) -> Judgement:
    """One claim's verdict. An unreadable response fails closed to unsupported."""
    data = _loads(raw)
    if "verdict" not in data:
        return Judgement(claim, Verdict.UNSUPPORTED, "judge returned no verdict")
    return Judgement(
        claim, Verdict.parse(data.get("verdict", "")), str(data.get("evidence", ""))
    )


def parse_coverage(raw: str) -> set[int]:
    covered = _loads(raw).get("facts_covered", [])
    return {int(i) for i in covered if str(i).lstrip("-").isdigit()}




_FENCE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.MULTILINE)


def _loads(raw: str) -> dict:
    """Parse JSON that may arrive wrapped in a code fence or with prose around it."""
    text = _FENCE.sub("", raw).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end <= start:
            return {}
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return {}


def parse_claims(raw: str) -> list[str]:
    claims = _loads(raw).get("claims", [])
    return [str(c).strip() for c in claims if str(c).strip()]




def summarise(
    listing: PropertyListing, judgements: list[Judgement], covered: set[int]
) -> GroundingResult:
    facts = key_facts(listing)
    valid = {i for i in covered if 0 <= i < len(facts)}
    return GroundingResult(
        judgements=judgements, facts_total=len(facts), facts_covered=len(valid)
    )
