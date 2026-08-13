"""Recover which key facts the judge credited, for generations already logged.

Run with:  uv run python scripts/backfill_coverage_indices.py

SPENDS MONEY, but barely — one coverage call per generation in the worksheet.

Earlier runs recorded only the number of facts covered, so the judge's coverage
decisions cannot be compared against human ticks. This recovers the indices for
those runs rather than regenerating them.

Writes data/coverage_judge.json. The eval logs are the graded artefact and are
not modified.
"""

from __future__ import annotations

import asyncio
import json

from inspect_ai.log import list_eval_logs, read_eval_log
from inspect_ai.model import get_model

from lodgify_challenge.calibration import generation_hash
from lodgify_challenge.config import REPO_ROOT, load_settings
from lodgify_challenge.grounding import build_coverage_prompt, key_facts, parse_coverage
from lodgify_challenge.listing import PropertyListing
from lodgify_challenge.tasks import GEN_V0_TASK_NAME, GEN_V1_TASK_NAME

PROPERTIES = ("villa_sitges", "apartment_porto_sparse")
OUT = REPO_ROOT / "data" / "coverage_judge.json"


def targets():
    runs = [
        read_eval_log(i)
        for i in sorted(list_eval_logs(str(REPO_ROOT / "logs")), key=lambda i: i.name)
    ]
    for version, task_name in (("v0", GEN_V0_TASK_NAME), ("v1", GEN_V1_TASK_NAME)):
        matching = [r for r in runs if r.eval.task.endswith(task_name) and len(r.samples) >= 8]
        if not matching:
            continue
        seen = set()
        for sample in matching[-1].samples:
            sid = str(sample.id)
            if sid in PROPERTIES and sid not in seen:
                seen.add(sid)
                yield version, sid, sample


async def main() -> None:
    settings = load_settings()
    settings.export()
    model = get_model(settings.judge_model)

    work = list(targets())
    print(f"re-judging coverage for {len(work)} generations")

    responses = await asyncio.gather(
        *(
            model.generate(
                build_coverage_prompt(
                    PropertyListing.model_validate(s.metadata["listing"]),
                    s.output.completion,
                )
            )
            for _, _, s in work
        )
    )

    out = {}
    for (version, sid, sample), response in zip(work, responses):
        listing = PropertyListing.model_validate(sample.metadata["listing"])
        total = len(key_facts(listing))
        covered = sorted(i for i in parse_coverage(response.completion) if 0 <= i < total)
        out[generation_hash(sample.output.completion)] = {
            "property": sid,
            "version": version,
            "facts_total": total,
            "covered_indices": covered,
        }
        print(f"  {sid:24} {version}  {len(covered)}/{total} facts credited")

    OUT.write_text(json.dumps(out, indent=2) + "\n")
    print(f"\nwritten to {OUT.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    asyncio.run(main())
