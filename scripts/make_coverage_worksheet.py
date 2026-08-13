"""Build the human worksheet for calibrating the judge's coverage decisions.

Run with:  uv run python scripts/make_coverage_worksheet.py

Precision is calibrated against human labels; recall is not. The judge decides
which key facts a piece of copy conveys, and nothing checks it. A token-overlap
proxy puts coverage ~18 points below the judge's figure, and that gap is either
the judge correctly crediting paraphrase or the judge being systematically
generous. This worksheet is what tells the two apart.

Scoped deliberately: two properties — one realistic, one sparse — across both
prompt versions. Same properties in both, so the answer also shows whether the
judge's generosity depends on copy style: v1's copy is markedly terser, which is
the harder case for recognising a rephrased fact.

The judge's own answers are not shown, for the same reason as the verdict
worksheet.
"""

from __future__ import annotations

import json

from inspect_ai.log import list_eval_logs, read_eval_log

from lodgify_challenge.calibration import TODO, generation_hash
from lodgify_challenge.config import REPO_ROOT
from lodgify_challenge.grounding import key_facts
from lodgify_challenge.listing import PropertyListing
from lodgify_challenge.tasks import GEN_V0_TASK_NAME, GEN_V1_TASK_NAME

PROPERTIES = ("villa_sitges", "apartment_porto_sparse")


def latest(task_name: str):
    runs = [
        read_eval_log(i)
        for i in sorted(list_eval_logs(str(REPO_ROOT / "logs")), key=lambda i: i.name)
    ]
    matching = [r for r in runs if r.eval.task.endswith(task_name) and len(r.samples) >= 8]
    if not matching:
        raise SystemExit(f"No 8-property run for {task_name} in logs/.")
    return matching[-1]


def main() -> None:
    md = [
        "# Coverage worksheet — calibrating recall",
        "",
        "For each property, read the copy and tick which of the key facts it",
        "**conveys**. A fact counts as conveyed if a reader would come away knowing",
        "it — rephrasing is fine (\"room for eight\" conveys \"sleeps 8\"), but",
        "implying something adjacent is not.",
        "",
        "Write your answers into `data/coverage_labels.jsonl` using the rows in",
        "`data/coverage_template.jsonl`: set `covered` to `true` or `false`.",
        "",
        "The judge's own answers are not shown here on purpose.",
        "",
    ]
    rows = []

    for version, task_name in (("v0", GEN_V0_TASK_NAME), ("v1", GEN_V1_TASK_NAME)):
        run = latest(task_name)
        seen = set()
        for sample in run.samples:
            if str(sample.id) not in PROPERTIES or str(sample.id) in seen:
                continue
            seen.add(str(sample.id))

            listing = PropertyListing.model_validate(sample.metadata["listing"])
            facts = key_facts(listing)
            digest = generation_hash(sample.output.completion)

            md += [
                "---",
                "",
                f"## {sample.id} — {version}",
                "",
                f"`generation_sha256: {digest}`",
                "",
                "### The copy",
                "",
                "```",
                sample.output.completion.strip(),
                "```",
                "",
                "### Facts — which does the copy convey?",
                "",
            ]
            for i, fact in enumerate(facts):
                md.append(f"{i}. {fact}")
                rows.append(
                    {
                        "generation_sha256": digest,
                        "property": str(sample.id),
                        "version": version,
                        "fact_index": i,
                        "fact": fact,
                        "covered": TODO,
                    }
                )
            md.append("")

    data = REPO_ROOT / "data"
    (data / "coverage_worksheet.md").write_text("\n".join(md) + "\n")
    (data / "coverage_template.jsonl").write_text(
        "\n".join(json.dumps(r) for r in rows) + "\n"
    )
    print(f"{len(rows)} fact judgements across {len(rows) // 2 // len(PROPERTIES)} facts/property")
    print("  data/coverage_worksheet.md")
    print("  data/coverage_template.jsonl")


if __name__ == "__main__":
    main()
