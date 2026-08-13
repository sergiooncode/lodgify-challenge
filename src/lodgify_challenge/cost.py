"""Projected spend for an eval run, before spending it.

The budget-limited key makes run shape a design constraint, not an afterthought:
whether the grounding scorer verifies claims one call at a time or in one batched
call changes the bill by an order of magnitude, and epochs multiply everything.
This models that so the choice is made on numbers.

Token counting is injected. Tests pass a stub and never reach the network;
`anthropic_token_counter` supplies the real one for a live estimate.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass

TokenCounter = Callable[[str], int]


@dataclass(frozen=True)
class Price:
    """Published rate per million tokens."""

    input_per_mtok: float
    output_per_mtok: float

    def cost(self, input_tokens: int, output_tokens: int) -> float:
        return (
            input_tokens / 1_000_000 * self.input_per_mtok
            + output_tokens / 1_000_000 * self.output_per_mtok
        )


PRICING: dict[str, Price] = {
    "claude-sonnet-5": Price(3.00, 15.00),
    "claude-opus-5": Price(5.00, 25.00),
    "claude-haiku-4-5": Price(1.00, 5.00),
}

SONNET_5_INTRO = Price(2.00, 10.00)
"""Introductory rate, through 2026-08-31. Estimate at the standard rate and
treat this as headroom rather than budgeting against a date that expires."""


@dataclass(frozen=True)
class CallProfile:
    """One kind of model call made while scoring a single sample."""

    name: str
    calls_per_sample: float
    input_tokens: int
    output_tokens: int

    def tokens_for(self, samples: int, epochs: int) -> tuple[int, int]:
        n = self.calls_per_sample * samples * epochs
        return round(n * self.input_tokens), round(n * self.output_tokens)


@dataclass(frozen=True)
class Line:
    name: str
    calls: float
    input_tokens: int
    output_tokens: int
    cost: float


@dataclass(frozen=True)
class Estimate:
    lines: Sequence[Line]
    samples: int
    epochs: int

    @property
    def total(self) -> float:
        return sum(line.cost for line in self.lines)

    @property
    def dominant(self) -> Line | None:
        """The line to attack first when the total is too high."""
        return max(self.lines, key=lambda line: line.cost, default=None)

    def table(self) -> str:
        width = max((len(line.name) for line in self.lines), default=0)
        rows = [
            f"{line.name:<{width}}  {line.calls:>7.0f} calls  "
            f"{line.input_tokens:>9,} in  {line.output_tokens:>8,} out  ${line.cost:>7.4f}"
            for line in self.lines
        ]
        rows.append(f"{'TOTAL':<{width}}  {'':>7}         {'':>9}      {'':>8}      ${self.total:>7.4f}")
        return "\n".join(rows)


def estimate_run(
    profiles: Iterable[CallProfile],
    *,
    samples: int,
    epochs: int = 1,
    price: Price,
) -> Estimate:
    lines = []
    for profile in profiles:
        input_tokens, output_tokens = profile.tokens_for(samples, epochs)
        lines.append(
            Line(
                name=profile.name,
                calls=profile.calls_per_sample * samples * epochs,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost=price.cost(input_tokens, output_tokens),
            )
        )
    return Estimate(lines=lines, samples=samples, epochs=epochs)


PROPERTY_TOKENS = 536
"""Mean tokens per fixture, measured with `count_tokens` on claude-sonnet-5
(range 364–701 across the four fixtures)."""

GENERATOR_SYSTEM_TOKENS = 400
GENERATED_COPY_TOKENS = 600
EXTRACTION_SYSTEM_TOKENS = 300
EXTRACTED_CLAIMS_TOKENS = 350
CLAIMS_PER_SAMPLE = 15
VERIFY_SYSTEM_TOKENS = 250
"""Assumed, not measured — nothing has generated copy yet. Re-derive these from
the first real run's log rather than trusting them; they are the weakest input
to every number below."""


def grounding_profiles(*, verify: str = "batched") -> list[CallProfile]:
    """Call profiles for one sample through generate → extract → verify.

    `verify="per_claim"` issues one call per extracted claim; `"batched"` sends
    every claim in a single call. Same measurement, very different bill — which
    is the point of modelling it before building it.
    """
    profiles = [
        CallProfile(
            "generate",
            calls_per_sample=1,
            input_tokens=GENERATOR_SYSTEM_TOKENS + PROPERTY_TOKENS,
            output_tokens=GENERATED_COPY_TOKENS,
        ),
        CallProfile(
            "extract claims",
            calls_per_sample=1,
            input_tokens=EXTRACTION_SYSTEM_TOKENS + PROPERTY_TOKENS + GENERATED_COPY_TOKENS,
            output_tokens=EXTRACTED_CLAIMS_TOKENS,
        ),
    ]

    if verify == "per_claim":
        profiles.append(
            CallProfile(
                "verify (per claim)",
                calls_per_sample=CLAIMS_PER_SAMPLE,
                input_tokens=VERIFY_SYSTEM_TOKENS + PROPERTY_TOKENS + 40,
                output_tokens=60,
            )
        )
    elif verify == "batched":
        profiles.append(
            CallProfile(
                "verify (batched)",
                calls_per_sample=1,
                input_tokens=VERIFY_SYSTEM_TOKENS + PROPERTY_TOKENS + EXTRACTED_CLAIMS_TOKENS,
                output_tokens=CLAIMS_PER_SAMPLE * 60,
            )
        )
    else:
        raise ValueError(f"unknown verify mode: {verify!r}")

    return profiles


def anthropic_token_counter(client: object, model: str) -> TokenCounter:
    """Adapt the Anthropic client to the TokenCounter shape.

    Counting is free but needs a key and the network, so it is never the default
    path — callers opt in.
    """

    def count(text: str) -> int:
        response = client.messages.count_tokens(  # type: ignore[attr-defined]
            model=model, messages=[{"role": "user", "content": text}]
        )
        return int(response.input_tokens)

    return count
