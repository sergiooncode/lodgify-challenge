"""raw → canonical, and the vocabulary that licenses amenity wording.

This is the only module that imports `raw`, so the brief's field names stop here.

It normalises and never repairs. Nothing is clamped, defaulted, or sanitised:
a negative bedroom count passes through, and so does an injection buried in
owner HTML — see `strip_html`.
"""

from __future__ import annotations

import html
import re

from lodgify_challenge.domain.listing import PropertyListing
from lodgify_challenge.domain.raw import RawProperty

AMENITY_LABELS: dict[str, str] = {
    "InternetBroadband": "broadband internet",
    "DishWasher": "dishwasher",
    "AirConditioning": "air conditioning",
    "BathroomAndLaundry": "bathroom and laundry facilities",
    "FreeParkingOnPremises": "free parking on the premises",
    "Heating": "heating",
    "KitchenAndDining": "kitchen and dining facilities",
    "SwimmingPool": "swimming pool",
}
"""Input data, not generator invention — and the grounding scorer's ground truth.

Labels are minimal and literal. `InternetBroadband` licenses "broadband
internet" and nothing more: not "free", not "high-speed", not "fast WiFi". Every
adjective this map does not license is a hallucination the grounding scorer must
catch, so widening a label here quietly widens what counts as supported.

Covers only the codes the fixtures use. An exhaustive map would be scaffolding
built ahead of anything that needs it."""

TYPE_LABELS: dict[str, str] = {
    "Villa": "villa",
    "NormalApartment": "apartment",
    "Cottage": "cottage",
}
"""`NormalApartment` is an internal code, not English. Copy that says "normal
apartment" has leaked a database value into marketing text."""

_TAG = re.compile(r"<[^>]+>")
_COMMENT = re.compile(r"<!--(.*?)-->", re.DOTALL)
_WHITESPACE = re.compile(r"\s+")


def strip_html(markup: str) -> str:
    """Remove tags, keep text — including the text inside HTML comments.

    Preserving comment contents is deliberate. The adversarial fixture hides a
    prompt injection in an HTML comment, and discarding comments here would
    silently mitigate it: the injection would never reach the model, Phase 7
    would report no vulnerability, and the report would be wrong. Sanitising is
    a legitimate defence, but it belongs where it can be measured and its cost
    stated — not hidden in a parsing helper.
    """
    text = _COMMENT.sub(r" \1 ", markup)
    text = _TAG.sub(" ", text)
    return _WHITESPACE.sub(" ", html.unescape(text)).strip()


def amenity_label(code: str) -> str | None:
    return AMENITY_LABELS.get(code)


def type_label(code: str) -> str:
    """Unknown types fall back to the raw code rather than a guess.

    A wrong-but-fluent label would be indistinguishable from a real one in the
    output; a leaked code is visible and gets caught.
    """
    return TYPE_LABELS.get(code, code)


def listing_from_json(text: str) -> PropertyListing:
    """Parse a fixture straight to canonical form.

    Callers get a `PropertyListing` and never touch `RawProperty`, which is what keeps
    the raw import contained to this module.
    """
    return to_listing(RawProperty.model_validate_json(text))


def to_listing(raw: RawProperty) -> PropertyListing:
    labels: list[str] = []
    unmapped: list[str] = []
    for code in raw.amenities:
        label = amenity_label(code)
        if label is None:
            unmapped.append(code)
        else:
            labels.append(label)

    return PropertyListing(
        property_id=raw.property_id,
        name=raw.property_name,
        type_label=type_label(raw.property_type),
        headline=raw.description.headline,
        description=strip_html(raw.description.description),
        amenity_labels=labels,
        amenity_codes=list(raw.amenities),
        unmapped_amenity_codes=unmapped,
        reviews=list(raw.reviews),
        review_count=raw.num_of_reviews,
        review_score=raw.average_review_score,
        max_guests=raw.rental_info.max_guests,
        bedrooms=raw.rental_info.bedrooms,
        bathrooms=raw.rental_info.bathrooms,
        city=raw.location.city,
        country=raw.location.country,
        latitude=raw.location.latitude,
        longitude=raw.location.longitude,
        cancellation_policy=raw.policies.cancellation_policy,
        payment_schedule=raw.policies.payment_schedule,
        damage_deposit=raw.policies.damage_deposit,
        check_in_time=raw.house_rules.check_in_time,
        check_out_time=raw.house_rules.check_out_time,
    )
