"""The brief's input object, verbatim.

Field names here mirror the brief exactly and appear nowhere else in the
codebase — `adapters` is the only module allowed to import from here, so a
change to the upstream shape has exactly one place to land. A structural test
enforces that.

Nothing validates plausibility. `bedrooms: -2` parses, a review score of 7.4 out
of 5 parses, a check-in time of "25 PM" parses. Absurd values have to reach the
scorers to be measured; a schema that rejected them would move the failure from
a reported metric to an import error.
"""

from __future__ import annotations

from pydantic import BaseModel


class RawDescription(BaseModel):
    name: str
    headline: str
    description: str


class RawRentalInfo(BaseModel):
    max_guests: int
    bedrooms: int
    bathrooms: int


class RawLocation(BaseModel):
    city: str
    country: str
    latitude: float
    longitude: float


class RawPolicies(BaseModel):
    cancellation_policy: str | None = None
    payment_schedule: str | None = None
    damage_deposit: str | None = None


class RawHouseRules(BaseModel):
    check_in_time: str
    check_out_time: str


class RawProperty(BaseModel):
    property_id: int
    property_name: str
    property_type: str
    description: RawDescription
    amenities: list[str]
    image_urls: list[str]
    reviews: list[str]
    num_of_reviews: int
    average_review_score: float
    rental_info: RawRentalInfo
    location: RawLocation
    policies: RawPolicies
    house_rules: RawHouseRules
