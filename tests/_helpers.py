"""Shared test data. A module rather than conftest fixtures because both
test files use these as plain values and factories, not injected fixtures."""

from __future__ import annotations

from lodgify_challenge.domain.listing import PropertyListing

CLEAN = """## HERO HEADLINE
Hillside villa in Sitges with room for eight

## HIGHLIGHTS
- Four bedrooms and three bathrooms
- Broadband internet
- Air conditioning

## ABOUT THIS PLACE
A stone villa above Sitges with a south-facing terrace.

## AMENITIES
Broadband internet, a dishwasher and air conditioning.
"""


def listing(**overrides: object) -> PropertyListing:
    base = dict(
        property_id=1,
        name="Casa Miramar",
        type_label="villa",
        headline="Hillside villa",
        description="A villa.",
        amenity_labels=["broadband internet", "air conditioning"],
        amenity_codes=["InternetBroadband", "AirConditioning"],
        unmapped_amenity_codes=[],
        reviews=[],
        review_count=0,
        review_score=0.0,
        max_guests=8,
        bedrooms=4,
        bathrooms=3,
        city="Sitges",
        country="Spain",
        latitude=41.2,
        longitude=1.8,
        cancellation_policy=None,
        payment_schedule=None,
        damage_deposit=None,
        check_in_time="4 PM",
        check_out_time="11 AM",
    )
    base.update(overrides)
    return PropertyListing.model_validate(base)
