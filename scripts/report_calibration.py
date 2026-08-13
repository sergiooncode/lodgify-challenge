"""Report judge agreement against the human gold labels. No API calls.

Run with:  uv run python scripts/report_calibration.py

Reads `data/gold_labels.jsonl` and the frozen run, and reports bias (agreement)
only. Variance (self-consistency) needs repeated judging passes and is reported
separately once those exist.
"""

from __future__ import annotations

from inspect_ai.log import list_eval_logs, read_eval_log

from lodgify_challenge.analysis.calibration import compare, generation_hash, load_labels
from lodgify_challenge.config import REPO_ROOT
from lodgify_challenge.eval.grounding import Verdict
from lodgify_challenge.eval.tasks import GEN_V0_TASK_NAME

LABELS = REPO_ROOT / "data" / "gold_labels.jsonl"


def judged_verdicts() -> dict[tuple[str, str], Verdict]:
    """Verdicts from the run the labels were written against.

    Deliberately not "the latest v0 run". Labels join by hash of the generation
    text, so a later run over a different fixture set orphans all of them —
    which the hash join makes loud, but which is avoidable by pinning here. Any
    v0 run containing a labelled generation is the right one.
    """
    labelled_hashes = {label.generation_sha256 for label in load_labels(LABELS)}

    runs = [
        read_eval_log(i)
        for i in sorted(list_eval_logs(str(REPO_ROOT / "logs")), key=lambda i: i.name)
    ]
    matching = [r for r in runs if r.eval.task.endswith(GEN_V0_TASK_NAME)]
    if not matching:
        raise SystemExit("No gen_v0 run in logs/.")

    def covers(run) -> int:
        return sum(
            1
            for s in run.samples
            if generation_hash(s.output.completion) in labelled_hashes
        )

    best = max(matching, key=covers)
    if not covers(best):
        raise SystemExit(
            "No run in logs/ contains the labelled generations. The labels were "
            "written against a run that is no longer present."
        )

    out: dict[tuple[str, str], Verdict] = {}
    for sample in best.samples:
        grounding = sample.scores.get("grounding")
        if grounding is None:
            continue
        digest = generation_hash(sample.output.completion)
        for j in grounding.metadata["judgements"]:
            out[(digest, j["claim"])] = Verdict.parse(j["verdict"])
    return out


def main() -> None:
    labels = load_labels(LABELS)
    if not labels:
        raise SystemExit(
            f"No labelled rows in {LABELS}.\n"
            "Fill in verdicts from data/labelling_template.jsonl first "
            "(rows still marked TODO(human) are skipped)."
        )

    agreement = compare(labels, judged_verdicts())

    print(f"labels read        {len(labels)}")
    print(f"matched to judge   {agreement.n}")
    if agreement.unmatched_labels:
        print(
            f"UNMATCHED          {agreement.unmatched_labels} "
            "— generations changed since labelling; labels are orphaned"
        )
    if not agreement.n:
        return

    print(f"\nraw agreement      {agreement.raw:.2f}")
    print(f"Cohen's kappa      {agreement.kappa:.2f}")

    detail = agreement.disagreement_detail()
    if not detail:
        print("\nno disagreements")
        return

    print(f"\ndisagreements ({len(detail)}):")
    for claim, human, judge, note in detail:
        print(f"\n  claim  {claim}")
        print(f"  human  {human}")
        print(f"  judge  {judge}")
        if note:
            print(f"  note   {note}")


if __name__ == "__main__":
    main()
