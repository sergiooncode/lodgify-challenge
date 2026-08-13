"""Run the generator and every scorer against the real model. SPENDS MONEY.

Run with:  uv run python scripts/run_eval.py

Goes through `load_settings().export()` rather than the bare `inspect eval` CLI:
Inspect's own dotenv lookup walks up the directory tree looking only for `.env`,
so it never sees `.env.local` and fails with "No ANTHROPIC_API_KEY defined".
"""

from __future__ import annotations

from inspect_ai import eval as inspect_eval

from lodgify_challenge.config import load_settings
from lodgify_challenge.eval.tasks import generate_copy_v0


def main() -> None:
    settings = load_settings()
    settings.export()

    logs = inspect_eval(
        generate_copy_v0(judge=settings.judge_model),
        model=settings.generator_model,
        log_dir=str(settings.log_dir),
    )
    for log in logs:
        print(f"status: {log.status}")
        if log.error:
            print(f"error: {log.error}")
        for score in log.results.scores if log.results else []:
            metrics = ", ".join(f"{k}={v.value:.2f}" for k, v in score.metrics.items())
            print(f"  {score.name:32} {metrics}")


if __name__ == "__main__":
    main()
