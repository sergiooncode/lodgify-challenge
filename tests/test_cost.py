import pytest

from lodgify_challenge.analysis.cost import (
    CLAIMS_PER_SAMPLE,
    EXTRACTION_SYSTEM_TOKENS,
    GENERATED_COPY_TOKENS,
    EXTRACTED_CLAIMS_TOKENS,
    GENERATOR_SYSTEM_TOKENS,
    PRICING,
    PROPERTY_TOKENS,
    VERIFY_SYSTEM_TOKENS,
    CallProfile,
    Price,
    anthropic_token_counter,
    estimate_run,
    grounding_profiles,
)

FLAT = Price(input_per_mtok=1.0, output_per_mtok=10.0)


def test_price_charges_input_and_output_separately() -> None:
    assert FLAT.cost(1_000_000, 0) == 1.0
    assert FLAT.cost(0, 1_000_000) == 10.0


def test_epochs_multiply_every_line() -> None:
    profile = CallProfile("generate", calls_per_sample=1, input_tokens=1000, output_tokens=500)
    one = estimate_run([profile], samples=4, epochs=1, price=FLAT)
    five = estimate_run([profile], samples=4, epochs=5, price=FLAT)
    assert five.total == pytest.approx(one.total * 5)


def test_epochs_default_to_one() -> None:
    profile = CallProfile("generate", calls_per_sample=1, input_tokens=1000, output_tokens=0)
    assert estimate_run([profile], samples=4, price=FLAT).lines[0].calls == 4


def test_reported_call_count_scales_with_epochs() -> None:
    """The call count drives rate-limit judgements, not just the bill — a
    mutation that divided by epochs instead of multiplying went unnoticed until
    this asserted it."""
    profile = CallProfile("verify", calls_per_sample=15, input_tokens=100, output_tokens=10)
    assert estimate_run([profile], samples=4, epochs=1, price=FLAT).lines[0].calls == 60
    assert estimate_run([profile], samples=4, epochs=5, price=FLAT).lines[0].calls == 300


def test_fractional_calls_per_sample_are_supported() -> None:
    profile = CallProfile("judge", calls_per_sample=0.5, input_tokens=100, output_tokens=0)
    estimate = estimate_run([profile], samples=4, epochs=1, price=FLAT)
    assert estimate.lines[0].calls == 2
    assert estimate.lines[0].input_tokens == 200


def test_dominant_line_identifies_the_biggest_spender() -> None:
    cheap = CallProfile("generate", calls_per_sample=1, input_tokens=1000, output_tokens=0)
    pricey = CallProfile("verify", calls_per_sample=15, input_tokens=1500, output_tokens=100)
    estimate = estimate_run([cheap, pricey], samples=4, epochs=1, price=FLAT)
    assert estimate.dominant is not None
    assert estimate.dominant.name == "verify"


def test_per_claim_verification_costs_far_more_than_batched() -> None:
    per_claim = CallProfile("verify", calls_per_sample=15, input_tokens=1500, output_tokens=80)
    batched = CallProfile("verify", calls_per_sample=1, input_tokens=2500, output_tokens=1200)
    a = estimate_run([per_claim], samples=4, epochs=1, price=PRICING["claude-sonnet-5"])
    b = estimate_run([batched], samples=4, epochs=1, price=PRICING["claude-sonnet-5"])
    assert a.total > b.total * 3


def test_empty_estimate_is_free_and_has_no_dominant_line() -> None:
    estimate = estimate_run([], samples=4, epochs=1, price=FLAT)
    assert estimate.total == 0
    assert estimate.dominant is None


def test_table_renders_every_line_and_a_total() -> None:
    profile = CallProfile("generate", calls_per_sample=1, input_tokens=1000, output_tokens=500)
    rendered = estimate_run([profile], samples=4, epochs=1, price=FLAT).table()
    assert "generate" in rendered
    assert "TOTAL" in rendered


def test_grounding_profiles_cover_generate_extract_and_verify() -> None:
    names = [p.name for p in grounding_profiles()]
    assert names[0] == "generate"
    assert names[1] == "extract claims"
    assert "verify" in names[2]


def test_per_claim_verify_issues_one_call_per_claim() -> None:
    verify = grounding_profiles(verify="per_claim")[-1]
    assert verify.calls_per_sample == CLAIMS_PER_SAMPLE
    assert verify.name == "verify (per claim)"


def test_batched_verify_issues_a_single_call_carrying_every_claim() -> None:
    verify = grounding_profiles(verify="batched")[-1]
    assert verify.calls_per_sample == 1
    assert verify.output_tokens == CLAIMS_PER_SAMPLE * 60


def test_generate_profile_input_includes_the_property_and_the_system_prompt() -> None:
    generate = grounding_profiles()[0]
    assert generate.input_tokens == GENERATOR_SYSTEM_TOKENS + PROPERTY_TOKENS
    assert generate.output_tokens == GENERATED_COPY_TOKENS


def test_extraction_profile_reads_both_the_property_and_the_generated_copy() -> None:
    extract = grounding_profiles()[1]
    assert extract.input_tokens == (
        EXTRACTION_SYSTEM_TOKENS + PROPERTY_TOKENS + GENERATED_COPY_TOKENS
    )


def test_generate_and_extract_are_one_call_each_per_sample() -> None:
    generate, extract, _ = grounding_profiles()
    assert generate.calls_per_sample == 1
    assert extract.calls_per_sample == 1


def test_per_claim_verify_input_is_the_system_prompt_property_and_one_claim() -> None:
    verify = grounding_profiles(verify="per_claim")[-1]
    assert verify.input_tokens == VERIFY_SYSTEM_TOKENS + PROPERTY_TOKENS + 40
    assert verify.output_tokens == 60


def test_batched_verify_input_carries_the_whole_extracted_claim_list() -> None:
    verify = grounding_profiles(verify="batched")[-1]
    assert verify.input_tokens == (
        VERIFY_SYSTEM_TOKENS + PROPERTY_TOKENS + EXTRACTED_CLAIMS_TOKENS
    )


def test_unknown_verify_mode_is_rejected_rather_than_silently_defaulting() -> None:
    with pytest.raises(ValueError, match="unknown verify mode"):
        grounding_profiles(verify="handwave")


def test_per_claim_verification_is_the_dominant_line_when_selected() -> None:
    estimate = estimate_run(
        grounding_profiles(verify="per_claim"),
        samples=4,
        epochs=1,
        price=PRICING["claude-sonnet-5"],
    )
    assert estimate.dominant is not None
    assert estimate.dominant.name == "verify (per claim)"


def test_token_counter_is_injected_and_never_hits_the_network() -> None:
    class StubMessages:
        def count_tokens(self, model: str, messages: list[dict[str, str]]) -> object:
            assert model == "claude-sonnet-5"
            return type("R", (), {"input_tokens": len(messages[0]["content"])})()

    class StubClient:
        messages = StubMessages()

    count = anthropic_token_counter(StubClient(), "claude-sonnet-5")
    assert count("abcd") == 4
