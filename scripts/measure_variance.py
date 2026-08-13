"""Judge self-consistency: re-judge the same frozen generations N times. SPENDS MONEY.

Run with:  uv run python scripts/measure_variance.py [passes]

Bias and variance answer different questions. Agreement with human labels says
whether the judge is systematically off; this says whether it gives the same
answer twice. A judge can be perfectly stable and stably wrong, or unbiased on
average and useless per claim.

Generations are held fixed — only the judging repeats — so any variation is the
judge's, not the generator's.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from inspect_ai.log import list_eval_logs, read_eval_log
from inspect_ai.model import get_model

from lodgify_challenge.analysis.calibration import generation_hash, self_consistency
from lodgify_challenge.config import REPO_ROOT
from lodgify_challenge.eval.grounding import (
    Verdict,
    build_claim_prompt,
    parse_claim_verdict,
)
from lodgify_challenge.domain.listing import PropertyListing
from lodgify_challenge.eval.tasks import GEN_V0_TASK_NAME

OUT = REPO_ROOT / "data" / "judge_variance.json"


def frozen_run():
    runs = [
        read_eval_log(i)
        for i in sorted(list_eval_logs(str(REPO_ROOT / "logs")), key=lambda i: i.name)
    ]
    matching = [r for r in runs if r.eval.task.endswith(GEN_V0_TASK_NAME)]
    if not matching:
        raise SystemExit("No gen_v0 run in logs/.")
    return matching[-1]


async def one_pass(model, work: list[tuple[str, PropertyListing, str]]) -> dict[str, Verdict]:
    """Re-judge every claim once. Claims are keyed by generation hash + text so
    passes line up even if ordering changes."""
    responses = await asyncio.gather(
        *(model.generate(build_claim_prompt(listing, claim)) for _, listing, claim in work)
    )
    return {
        f"{digest[:12]}::{claim}": parse_claim_verdict(r.completion, claim).verdict
        for (digest, _, claim), r in zip(work, responses)
    }


async def main() -> None:
    passes = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    from lodgify_challenge.config import load_settings

    settings = load_settings()
    settings.export()
    model = get_model(settings.judge_model)

    run = frozen_run()
    work: list[tuple[str, PropertyListing, str]] = []
    for sample in run.samples:
        grounding = sample.scores.get("grounding")
        if grounding is None:
            continue
        listing = PropertyListing.model_validate(sample.metadata["listing"])
        digest = generation_hash(sample.output.completion)
        for j in grounding.metadata["judgements"]:
            work.append((digest, listing, j["claim"]))

    print(f"re-judging {len(work)} claims x {passes} passes")
    results = [await one_pass(model, work) for _ in range(passes)]

    consistency = self_consistency(results)
    print(f"\nclaims compared    {consistency.n}")
    print(f"passes             {consistency.repeats}")
    print(f"stable share       {consistency.stable_share:.2f}")

    unstable = consistency.unstable()
    if unstable:
        print(f"\nunstable claims ({len(unstable)}):")
        for claim, verdicts in list(unstable.items())[:20]:
            print(f"  {claim.split('::', 1)[1][:60]}")
            print(f"      {' -> '.join(str(v) for v in verdicts)}")

    OUT.write_text(
        json.dumps(
            {
                "passes": consistency.repeats,
                "claims": consistency.n,
                "stable_share": consistency.stable_share,
                "per_claim": {k: [str(v) for v in vs] for k, vs in consistency.per_claim.items()},
            },
            indent=2,
        )
        + "\n"
    )
    print(f"\nwritten to {OUT.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    asyncio.run(main())
