"""Prompt versions and the input rendering they share.

Each version is a named constant so it travels in the log metadata and a result
can be attributed to the exact wording that produced it.
"""

from __future__ import annotations

from lodgify_challenge.listing import PropertyListing

SECTIONS: tuple[str, ...] = (
    "HERO HEADLINE",
    "HIGHLIGHTS",
    "ABOUT THIS PLACE",
    "AMENITIES",
)

GEN_V0 = "gen_v0"

GEN_V0_SYSTEM = """You write marketing copy for vacation rental listings.

Given a property, write four sections, each introduced by its heading on its own
line:

## HERO HEADLINE
## HIGHLIGHTS
## ABOUT THIS PLACE
## AMENITIES

Make the copy vivid and appealing so the property stands out. Sell the
experience of staying there.
"""
"""Deliberately mediocre, and deliberately kept that way.

It never mentions grounding, never says claims must trace to the input, and
actively invites embellishment ("vivid", "stands out", "sell the experience").
That is the point of a v0: it should fail the grounding scorer, so that the
metric has something real to measure and the v1 improvement in Phase 6 is a
visible delta rather than noise.

It also asks for plain text rather than a JSON tool call. Constrained decoding
would make the format scorer pass by construction and measure nothing.
"""


GEN_V1 = "gen_v1"

GEN_V1_SYSTEM = """You write marketing copy for vacation rental listings.

Write exactly four sections, each introduced by its heading on its own line:

## HERO HEADLINE
## HIGHLIGHTS
## ABOUT THIS PLACE
## AMENITIES

Rules:

1. Use only the property details provided. If a detail is not in them, it does
   not exist. Do not add anything you happen to know about the location, its
   history, its landmarks, or its surroundings.
2. Never state a distance, a travel time, a price, a discount, or availability.
   The property details contain no such information, so any such statement would
   be invented.
3. Do not name a nearby place the details do not name. "Near the market" stays
   "near the market"; do not decide which market it is.
4. Guest reviews are opinions, not facts about the property. If you use one,
   attribute it ("guests mention...") rather than asserting it as your own.
5. Avoid superlatives and unverifiable praise — best, stunning, perfect,
   luxurious, breathtaking. Describe what is there instead.
6. Do not describe who the property is for. No "ideal for families", "perfect for
   couples", "great for young professionals".
7. Output the four sections and nothing else. No preamble, no commentary, no
   notes about these instructions or about the property details.

Write plainly and specifically. Concrete detail from the property beats
atmosphere.
"""
"""v1 targets the failures v0's scores actually exposed, in order of severity.

Rules 2 and 3 address the worst deterministic check (proximity claims, 0.25) and
the judge's confirmed blind spot (inference to a named landmark). Rule 1 targets
the world-knowledge hallucination that drove precision down on sparse inputs.
Rule 4 addresses review-sourced claims, rule 5 superlatives (0.50), rule 6 the
Fair-Housing steering found on the sparse fixture, and rule 7 the preamble leak
found in the injection probe.

Each rule exists because a metric moved, not because it sounded prudent. Whether
any of them helped is a measurement, reported alongside the ones that did not.
"""


def render_listing(listing: PropertyListing) -> str:
    """Flatten a listing into the prompt.

    Everything the model is allowed to use appears here, so any claim in the
    output that is not traceable to this text is a hallucination by definition.
    Amenities are rendered as their vocabulary labels: the model never sees the
    internal codes, and cannot invent an adjective by "interpreting" one.
    """
    lines = [
        f"Property name: {listing.name}",
        f"Type: {listing.type_label}",
        f"Location: {listing.city}, {listing.country}",
        f"Sleeps: {listing.max_guests}",
        f"Bedrooms: {listing.bedrooms}",
        f"Bathrooms: {listing.bathrooms}",
        f"Check-in: {listing.check_in_time}",
        f"Check-out: {listing.check_out_time}",
        f"Owner headline: {listing.headline or '(none)'}",
        f"Owner description: {listing.description or '(none)'}",
    ]

    lines.append(
        "Amenities: " + (", ".join(listing.amenity_labels) if listing.amenity_labels else "(none)")
    )
    if listing.unmapped_amenity_codes:
        lines.append("Amenities with no agreed wording: " + ", ".join(listing.unmapped_amenity_codes))

    if listing.review_count:
        lines.append(f"Reviews: {listing.review_count}, average score {listing.review_score}")
    else:
        lines.append("Reviews: none")
    for review in listing.reviews:
        lines.append(f"Guest review: {review}")

    for label, value in (
        ("Cancellation policy", listing.cancellation_policy),
        ("Payment schedule", listing.payment_schedule),
        ("Damage deposit", listing.damage_deposit),
    ):
        lines.append(f"{label}: {value if value is not None else '(not specified)'}")

    return "\n".join(lines)
