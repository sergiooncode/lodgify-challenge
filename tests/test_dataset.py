from lodgify_challenge.eval.dataset import ADVERSARIAL, FIXTURE_DIR, property_samples
from lodgify_challenge.domain.prompts import render_listing
from lodgify_challenge.domain.adapters import listing_from_json


def test_every_fixture_becomes_a_sample() -> None:
    samples = property_samples()
    ids = {s.id for s in samples}
    assert ADVERSARIAL <= ids
    assert "villa_sitges" in ids
    assert len(samples) == len(list(FIXTURE_DIR.glob("*.json")))


def test_the_realistic_slice_is_not_a_single_property() -> None:
    """It was, for a while: three adversarial fixtures against one realistic one
    meant 'realistic performance' rested on a single anecdote."""
    realistic = [s for s in property_samples() if s.metadata["slice"] == "realistic"]
    assert len(realistic) > 1


def test_slice_is_recorded_at_build_time() -> None:
    by_id = {s.id: s for s in property_samples()}
    assert by_id["villa_sitges"].metadata["slice"] == "realistic"
    for name in ADVERSARIAL:
        assert by_id[name].metadata["slice"] == "adversarial"


def test_listing_travels_with_the_sample_for_later_grounding() -> None:
    sample = next(s for s in property_samples() if s.id == "villa_sitges")
    assert sample.metadata["listing"]["bedrooms"] == 4
    assert "broadband internet" in sample.metadata["listing"]["amenity_labels"]


def test_prompt_shows_labels_and_never_internal_codes() -> None:
    sample = next(s for s in property_samples() if s.id == "villa_sitges")
    assert "broadband internet" in sample.input
    assert "InternetBroadband" not in sample.input
    assert "NormalApartment" not in sample.input


def test_absurd_values_reach_the_prompt_unrepaired() -> None:
    sample = next(s for s in property_samples() if s.id == "absurd_values")
    assert "Bedrooms: -2" in sample.input
    assert "average score 7.4" in sample.input


def test_injection_reaches_the_prompt() -> None:
    """If the adapter or the renderer quietly dropped it, Phase 7 would report a
    clean bill of health for a system that was never actually tested."""
    sample = next(s for s in property_samples() if s.id == "cottage_injection")
    assert "Ignore all previous instructions" in sample.input


def test_sparse_property_renders_explicit_absences_not_blanks() -> None:
    sample = next(s for s in property_samples() if s.id == "apartment_porto_sparse")
    assert "Reviews: none" in sample.input
    assert "Cancellation policy: (not specified)" in sample.input
    assert "Owner headline: (none)" in sample.input


def test_render_is_pure_and_depends_only_on_the_listing(tmp_path) -> None:
    from lodgify_challenge.eval.dataset import FIXTURE_DIR

    listing = listing_from_json((FIXTURE_DIR / "villa_sitges.json").read_text())
    assert render_listing(listing) == render_listing(listing)
