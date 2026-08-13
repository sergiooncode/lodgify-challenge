"""Run v0 and v1 under identical conditions and compare. SPENDS MONEY (~$1.80).

Run with:  uv run python scripts/compare_versions.py [epochs]

Both versions share the dataset, the scorers, the judge and the epoch count, so
the only difference is the prompt. Epochs exist because a single generation per
property gives four paired observations, and four is not enough to distinguish a
real improvement from noise.

The comparison is reported per metric with a paired difference. It is
deliberately not dressed up as a significance test: with four properties the test
has almost no power, and a p-value here would imply a rigour the sample cannot
support. What is reported is the effect, its spread, and how many properties
moved which way.
"""

from __future__ import annotations

import sys
from statistics import mean, stdev

from inspect_ai import eval as inspect_eval

from lodgify_challenge.config import load_settings
from lodgify_challenge.tasks import generate_copy_v0, generate_copy_v1

METRICS = (
    "precision",
    "recall",
    "review_sourced_rate",
    "unsupportable_by_construction",
    "unverifiable_superlatives",
    "discriminatory_language",
    "preamble_leakage",
    "required_sections",
)


def per_sample(log) -> dict[str, dict[str, float]]:
    """{metric: {sample_id: mean across epochs}}."""
    collected: dict[str, dict[str, list[float]]] = {m: {} for m in METRICS}
    for sample in log.samples:
        for name, score in (sample.scores or {}).items():
            value = score.value
            pairs = value.items() if isinstance(value, dict) else [(name, value)]
            for metric, number in pairs:
                if metric in collected and isinstance(number, (int, float)):
                    collected[metric].setdefault(str(sample.id), []).append(float(number))
    return {m: {sid: mean(v) for sid, v in by_id.items()} for m, by_id in collected.items()}


def main() -> None:
    epochs = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    settings = load_settings()
    settings.export()

    results = {}
    for label, task in (("v0", generate_copy_v0), ("v1", generate_copy_v1)):
        print(f"\n=== {label}: {epochs} epochs ===")
        log = inspect_eval(
            task(judge=settings.judge_model),
            model=settings.generator_model,
            log_dir=str(settings.log_dir),
            epochs=epochs,
        )[0]
        if log.status != "success":
            raise SystemExit(f"{label} run failed: {log.error}")
        results[label] = per_sample(log)

    print(f"\n{'metric':32}{'v0':>8}{'v1':>8}{'delta':>9}{'moved':>12}")
    print("-" * 69)
    for metric in METRICS:
        a, b = results["v0"][metric], results["v1"][metric]
        shared = sorted(set(a) & set(b))
        if not shared:
            continue
        diffs = [b[s] - a[s] for s in shared]
        better = sum(1 for d in diffs if d > 0)
        worse = sum(1 for d in diffs if d < 0)
        spread = f"±{stdev(diffs):.2f}" if len(diffs) > 1 else ""
        print(
            f"{metric:32}{mean(a[s] for s in shared):>8.2f}"
            f"{mean(b[s] for s in shared):>8.2f}"
            f"{mean(diffs):>+8.2f}  {spread:<7}"
            f"{f'{better} up / {worse} down':>14}"
        )

    print(f"\nProperties compared: {len(shared)}. Too few for a significance test —")
    print("the per-property direction is the honest summary, not a p-value.")


if __name__ == "__main__":
    main()
