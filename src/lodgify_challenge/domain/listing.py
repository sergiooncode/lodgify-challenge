"""The canonical model the rest of the pipeline works against.

Deliberately a different type in a different module from `raw`. The generator,
the scorers and the notebook all speak this shape, so the brief's field names
never leak past the adapter.

Like `raw`, this validates shape and not plausibility.
"""

from __future__ import annotations

from pydantic import BaseModel


class PropertyListing(BaseModel):
    property_id: int
    name: str
    type_label: str
    headline: str
    description: str

    amenity_labels: list[str]
    amenity_codes: list[str]
    unmapped_amenity_codes: list[str]
    """Codes with no entry in the vocabulary. Kept rather than dropped: an
    unmapped code licenses no adjective at all, so the grounding scorer needs to
    see it to judge any claim that leans on it."""

    reviews: list[str]
    review_count: int
    review_score: float

    max_guests: int
    bedrooms: int
    bathrooms: int

    city: str
    country: str
    latitude: float
    longitude: float

    cancellation_policy: str | None
    payment_schedule: str | None
    damage_deposit: str | None

    check_in_time: str
    check_out_time: str

    @property
    def has_reviews(self) -> bool:
        return bool(self.reviews)
