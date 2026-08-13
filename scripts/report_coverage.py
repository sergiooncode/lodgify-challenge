"""Judge coverage decisions against human ticks. No API calls.

Run with:  uv run python scripts/report_coverage.py

Answers one question: is the ~18-point gap between the judge's recall and a
token-overlap proxy the judge correctly crediting paraphrase, or the judge being
systematically generous?

The direction of disagreement is the whole point. A judge that ticks facts the
human did not is inflating recall; one that misses facts the human ticked is
deflating it. Raw agreement alone cannot tell those apart, so both are reported.
"""

from __future__ import annotations

import json
from collections import Counter

from inspect_ai.log import list_eval_logs, read_eval_log

from lodgify_challenge.analysis.calibration import TODO, cohens_kappa, generation_hash, raw_agreement
from lodgify_challenge.config import REPO_ROOT
from lodgify_challenge.eval.tasks import GEN_V0_TASK_NAME, GEN_V1_TASK_NAME

LABELS = REPO_ROOT / "data" / "coverage_labels.jsonl"


BACKFILL = REPO_ROOT / "data" / "coverage_judge.json"


def judged_coverage() -> dict[tuple[str, int], bool]:
    """{(generation hash, fact index): judge said covered}.

    Reads the logs first. Runs that predate the scorer storing indices fall back
    to the backfill file, which recovers them without regenerating the logs.
    """
    out: dict[tuple[str, int], bool] = {}

    runs = [
        read_eval_log(i)
        for i in sorted(list_eval_logs(str(REPO_ROOT / "logs")), key=lambda i: i.name)
    ]
    for task_name in (GEN_V0_TASK_NAME, GEN_V1_TASK_NAME):
        matching = [r for r in runs if r.eval.task.endswith(task_name) and len(r.samples) >= 8]
        for sample in (matching[-1].samples if matching else []):
            grounding = sample.scores.get("grounding")
            covered = grounding.metadata.get("covered_indices") if grounding else None
            if covered is None:
                continue
            digest = generation_hash(sample.output.completion)
            for i in range(grounding.metadata["facts_total"]):
                out[(digest, i)] = i in set(covered)

    if BACKFILL.is_file():
        for digest, entry in json.loads(BACKFILL.read_text()).items():
            covered = set(entry["covered_indices"])
            for i in range(entry["facts_total"]):
                out.setdefault((digest, i), i in covered)

    return out


def main() -> None:
    if not LABELS.is_file():
        raise SystemExit(
            f"No {LABELS.name}. Fill in data/coverage_template.jsonl first "
            "(rows still marked TODO(human) are skipped)."
        )

    labels = []
    for line in LABELS.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        row = json.loads(line)
        if str(row.get("covered")).strip() in ("", TODO):
            continue
        labels.append(row)

    if not labels:
        raise SystemExit("No completed rows — every 'covered' is still TODO(human).")

    judge = judged_coverage()
    if not judge:
        raise SystemExit(
            "The runs in logs/ record only the number of facts covered, not which "
            "ones. Re-run the eval after the scorer stores covered indices."
        )

    pairs, unmatched = [], 0
    disagreements = []
    for row in labels:
        key = (row["generation_sha256"], int(row["fact_index"]))
        if key not in judge:
            unmatched += 1
            continue
        human = str(row["covered"]).lower() in ("true", "yes", "1")
        pairs.append((human, judge[key]))
        if human != judge[key]:
            disagreements.append((row, judge[key]))

    print(f"labels read      {len(labels)}")
    print(f"matched          {len(pairs)}")
    if unmatched:
        print(f"UNMATCHED        {unmatched} — generations changed since labelling")
    if not pairs:
        return

    print(f"\nraw agreement    {raw_agreement(pairs):.2f}")
    print(f"Cohen's kappa    {cohens_kappa(pairs):.2f}")

    direction = Counter(
        "judge over-credits" if j and not h else "judge under-credits"
        for h, j in pairs
        if h != j
    )
    print(f"\ndisagreements    {sum(direction.values())}")
    for label, count in direction.most_common():
        print(f"  {label:22} {count}")

    if disagreements:
        print("\ndetail:")
        for row, judge_said in disagreements:
            print(
                f"  [{row['property']}/{row['version']}] fact {row['fact_index']}: "
                f"{row['fact'][:52]}"
            )
            print(f"      human={row['covered']}  judge={judge_said}")


if __name__ == "__main__":
    main()
