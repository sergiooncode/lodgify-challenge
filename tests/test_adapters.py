import ast
import json
from pathlib import Path

import pytest

from lodgify_challenge.domain.adapters import (
    AMENITY_LABELS,
    listing_from_json,
    strip_html,
    to_listing,
    type_label,
)
from lodgify_challenge.domain.raw import RawProperty

TESTS_ROOT = Path(__file__).resolve().parent.parent
FIXTURE_DIR = TESTS_ROOT / "data" / "fixtures"
SRC_DIR = TESTS_ROOT / "src" / "lodgify_challenge"
"""Anchored to this file, not to the package. Under a mutation-testing sandbox
the package is copied elsewhere while the tests run in place, so deriving data
paths from the package location points at a directory that does not exist."""


def fixture(name: str) -> str:
    return (FIXTURE_DIR / f"{name}.json").read_text()


@pytest.mark.parametrize("path", sorted(FIXTURE_DIR.glob("*.json")), ids=lambda p: p.stem)
def test_every_fixture_parses_and_adapts(path: Path) -> None:
    listing = listing_from_json(path.read_text())
    assert listing.property_id > 0
    assert listing.name


# --- shape, not plausibility -------------------------------------------------


def test_absurd_values_survive_the_adapter_unchanged() -> None:
    listing = listing_from_json(fixture("absurd_values"))
    assert listing.bedrooms == -2
    assert listing.bathrooms == 0
    assert listing.max_guests == 0
    assert listing.review_score == 7.4
    assert listing.review_count == -3
    assert listing.check_in_time == "25 PM"


def test_null_policies_stay_null_rather_than_becoming_empty_strings() -> None:
    listing = listing_from_json(fixture("apartment_porto_sparse"))
    assert listing.cancellation_policy is None
    assert listing.payment_schedule is None
    assert listing.damage_deposit is None


def test_populated_policies_are_carried_through_verbatim() -> None:
    """The null-policy test alone passes against an adapter that drops policies
    entirely — mutation testing surfaced exactly that survivor."""
    listing = listing_from_json(fixture("villa_sitges"))
    assert listing.cancellation_policy == "Free cancellation up to 14 days before arrival."
    assert listing.payment_schedule == "50% at booking, balance 30 days before arrival."
    assert listing.damage_deposit == "500 EUR, refundable within 7 days of checkout."


def test_scalar_fields_are_carried_through_verbatim() -> None:
    listing = listing_from_json(fixture("villa_sitges"))
    assert (listing.property_id, listing.name) == (1041, "Casa Miramar")
    assert (listing.max_guests, listing.bedrooms, listing.bathrooms) == (8, 4, 3)
    assert (listing.city, listing.country) == ("Sitges", "Spain")
    assert (listing.latitude, listing.longitude) == (41.2371, 1.8055)
    assert (listing.check_in_time, listing.check_out_time) == ("4 PM", "11 AM")
    assert listing.review_count == 87
    assert listing.review_score == 4.72
    assert listing.headline == "Hillside villa with sea views"
    assert listing.amenity_codes == [
        "InternetBroadband",
        "DishWasher",
        "AirConditioning",
        "BathroomAndLaundry",
        "FreeParkingOnPremises",
    ]
    assert len(listing.reviews) == 3


def test_strip_html_collapses_whitespace_around_recovered_comment_text() -> None:
    assert strip_html("<p>a</p><!-- b --><p>c</p>") == "a b c"


def test_sparse_listing_keeps_its_emptiness() -> None:
    listing = listing_from_json(fixture("apartment_porto_sparse"))
    assert listing.reviews == []
    assert listing.headline == ""
    assert not listing.has_reviews


# --- vocabulary --------------------------------------------------------------


def test_amenity_codes_map_to_minimal_literal_labels() -> None:
    listing = listing_from_json(fixture("villa_sitges"))
    assert "broadband internet" in listing.amenity_labels
    assert "air conditioning" in listing.amenity_labels


def test_no_label_licenses_an_adjective_the_code_does_not_carry() -> None:
    forbidden = ("high-speed", "fast", "luxury", "stunning", "spacious")
    for code, label in AMENITY_LABELS.items():
        assert not any(word in label.lower() for word in forbidden), code
    assert "free" in AMENITY_LABELS["FreeParkingOnPremises"]


def test_internal_type_codes_are_translated_not_leaked() -> None:
    assert type_label("NormalApartment") == "apartment"
    listing = listing_from_json(fixture("apartment_porto_sparse"))
    assert listing.type_label == "apartment"


def test_unknown_amenity_code_is_kept_as_unmapped_not_dropped() -> None:
    raw = json.loads(fixture("villa_sitges"))
    raw["amenities"].append("HeatedPrivatePool")
    listing = to_listing(RawProperty.model_validate(raw))
    assert "HeatedPrivatePool" in listing.unmapped_amenity_codes
    assert "HeatedPrivatePool" not in listing.amenity_labels
    assert "HeatedPrivatePool" in listing.amenity_codes


def test_unknown_type_code_falls_back_to_the_code_rather_than_a_guess() -> None:
    assert type_label("TreeHouseDeluxe") == "TreeHouseDeluxe"


# --- HTML normalisation ------------------------------------------------------


def test_tags_are_stripped_and_entities_decoded() -> None:
    assert strip_html("<p>Sea &amp; sand</p>") == "Sea & sand"


def test_injection_hidden_in_an_html_comment_is_preserved() -> None:
    listing = listing_from_json(fixture("cottage_injection"))
    assert "Ignore all previous instructions" in listing.description
    assert "<!--" not in listing.description
    assert "<p>" not in listing.description


def test_review_text_is_never_merged_into_the_description() -> None:
    listing = listing_from_json(fixture("cottage_injection"))
    assert "sauna" not in listing.description.lower()
    assert any("sauna" in review.lower() for review in listing.reviews)


# --- structural --------------------------------------------------------------


def test_the_structural_scan_actually_sees_the_package() -> None:
    """rglob, not glob: subpackages would make the two scans below silently
    vacuous — passing because they inspected nothing."""
    scanned = list(SRC_DIR.rglob("*.py"))
    assert len(scanned) >= 10, f"only {len(scanned)} modules scanned"
    assert any(p.name == "raw.py" for p in scanned)
    assert any(p.name == "adapters.py" for p in scanned)


def test_raw_module_is_imported_only_by_adapters() -> None:
    offenders = []
    for path in SRC_DIR.rglob("*.py"):
        if path.name in {"raw.py", "adapters.py"}:
            continue
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and (node.module or "").endswith("raw"):
                offenders.append(path.name)
            elif isinstance(node, ast.Import):
                offenders += [path.name for a in node.names if a.name.endswith(".raw")]
    assert not offenders, f"raw types must stay behind the adapter, leaked into: {offenders}"


def test_brief_field_names_do_not_appear_outside_raw_and_adapters() -> None:
    brief_only = ("num_of_reviews", "average_review_score", "rental_info", "house_rules")
    offenders = {}
    for path in SRC_DIR.rglob("*.py"):
        if path.name in {"raw.py", "adapters.py"}:
            continue
        text = path.read_text()
        found = [name for name in brief_only if name in text]
        if found:
            offenders[path.name] = found
    assert not offenders, f"brief field names leaked past the adapter: {offenders}"
