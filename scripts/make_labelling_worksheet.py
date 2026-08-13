"""Build the human labelling worksheet from the frozen run.

Run with:  uv run python scripts/make_labelling_worksheet.py

Writes two files:
  data/labelling_worksheet.md    — the evidence, for reading
  data/labelling_template.jsonl  — rows to fill in and copy to gold_labels.jsonl

**The judge's verdicts are deliberately absent from both.** Showing them would
anchor the labeller, and agreement would then measure suggestibility rather than
calibration.

Claims are stratified across the judge's verdict classes so all four are
represented — with ~90 claims and ~20 labels, uniform sampling would yield about
one review-sourced claim and nothing could be said about the category the whole
design turns on. The stratification is stated in the README, because it means
agreement is measured on a deliberately hard subset rather than a typical one.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from inspect_ai.log import list_eval_logs, read_eval_log

from lodgify_challenge.analysis.calibration import TODO, generation_hash
from lodgify_challenge.config import REPO_ROOT
from lodgify_challenge.eval.grounding import key_facts
from lodgify_challenge.domain.listing import PropertyListing
from lodgify_challenge.domain.prompts import render_listing
from lodgify_challenge.eval.tasks import GEN_V0_TASK_NAME

PER_CLASS = 2
PER_PROPERTY = 5


def frozen_run():
    runs = [read_eval_log(i) for i in sorted(list_eval_logs(str(REPO_ROOT / "logs")), key=lambda i: i.name)]
    matching = [r for r in runs if r.eval.task.endswith(GEN_V0_TASK_NAME)]
    if not matching:
        raise SystemExit("No gen_v0 run in logs/ — run the task first.")
    return matching[-1]


def select(sample) -> list[str]:
    """Up to PER_CLASS claims from each judge verdict class, deterministically."""
    by_verdict: dict[str, list[str]] = defaultdict(list)
    for j in sample.scores["grounding"].metadata["judgements"]:
        by_verdict[j["verdict"]].append(j["claim"])

    chosen: list[str] = []
    for verdict in ("supported", "contradicted", "unsupported", "review_sourced"):
        chosen += by_verdict.get(verdict, [])[:PER_CLASS]
    return chosen[:PER_PROPERTY]


def main() -> None:
    run = frozen_run()
    md: list[str] = [
        "# Labelling worksheet — judge calibration",
        "",
        "For each claim, decide which verdict a careful person would give, using",
        "only the evidence shown. Write your verdicts into",
        "`data/gold_labels.jsonl` using the rows in `data/labelling_template.jsonl`.",
        "",
        "The judge's own verdicts are not shown here on purpose.",
        "",
        "## The four verdicts",
        "",
        "- **supported** — the STRUCTURED DATA below directly supports it.",
        "- **contradicted** — the STRUCTURED DATA directly contradicts it.",
        "- **review_sourced** — only a GUEST REVIEW supports it, not the structured",
        "  data. Never mark these supported: an owner republishing a guest's opinion",
        "  as their own marketing claim is a distinct risk.",
        "- **unsupported** — nothing here establishes it. Includes world knowledge,",
        "  and anything about price, availability or distance, since the schema has",
        "  no such fields.",
        "",
    ]
    rows: list[dict] = []

    for sample in run.samples:
        listing = PropertyListing.model_validate(sample.metadata["listing"])
        digest = generation_hash(sample.output.completion)
        claims = select(sample)
        if not claims:
            continue

        structured = render_listing(listing)
        for review in listing.reviews:
            structured = structured.replace(f"Guest review: {review}\n", "").replace(
                f"Guest review: {review}", ""
            )

        md += [
            "---",
            "",
            f"## {sample.id}  ({sample.metadata['slice']})",
            "",
            f"`generation_sha256: {digest}`",
            "",
            "### Structured data",
            "",
            "```",
            structured.strip(),
            "```",
            "",
            "### Guest reviews",
            "",
        ]
        md += [f"- {r}" for r in listing.reviews] or ["(none)"]
        md += ["", "### Key facts the copy is expected to convey", ""]
        md += [f"{i}. {f}" for i, f in enumerate(key_facts(listing))]
        md += ["", "### Claims to label", ""]

        for n, claim in enumerate(claims, 1):
            md.append(f"{n}. `{claim}`")
            rows.append(
                {"generation_sha256": digest, "claim": claim, "verdict": TODO, "note": ""}
            )
        md.append("")

    data = REPO_ROOT / "data"
    (data / "labelling_worksheet.md").write_text("\n".join(md) + "\n")
    (data / "labelling_template.jsonl").write_text(
        "\n".join(json.dumps(r) for r in rows) + "\n"
    )
    print(f"{len(rows)} claims across {len(run.samples)} properties")
    print("  data/labelling_worksheet.md")
    print("  data/labelling_template.jsonl")


if __name__ == "__main__":
    main()
