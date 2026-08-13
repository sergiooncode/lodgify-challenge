"""Minimal Task used to settle PLAN Phase 0.

The brief's reproducibility requirement rests entirely on a committed `.eval` log
re-opening with no API call. This proves the mechanism before any scorer is
written, so the whole design isn't built on an assumption about log replay.
"""

from inspect_ai import Task, task
from inspect_ai.dataset import Sample
from inspect_ai.scorer import includes
from inspect_ai.solver import generate, system_message

from lodgify_challenge.eval.dataset import property_dataset
from lodgify_challenge.domain.prompts import GEN_V0, GEN_V0_SYSTEM, GEN_V1, GEN_V1_SYSTEM
from lodgify_challenge.eval.scorers import deterministic_scorers, grounding

PROBE_TOKEN = "PROBE-OK"
GEN_V0_TASK_NAME = f"generate_copy_{GEN_V0}"
GEN_V1_TASK_NAME = f"generate_copy_{GEN_V1}"


@task
def replay_probe() -> Task:
    return Task(
        dataset=[Sample(input=f"Reply with exactly: {PROBE_TOKEN}", target=PROBE_TOKEN)],
        solver=generate(),
        scorer=includes(),
    )


@task
def generate_copy_v0(judge: str | None = None) -> Task:
    """v0: deliberately mediocre — told to be vivid, never told to stay grounded."""
    return _copy_task(GEN_V0_TASK_NAME, GEN_V0_SYSTEM, GEN_V0, judge)


def _copy_task(name: str, system: str, version: str, judge: str | None) -> Task:
    """Shared shape for every generator version.

    Versions are separate named tasks rather than one parameterised task, so a
    log identifies which wording produced it and results never blur across
    versions.
    """
    return Task(
        name=name,
        dataset=property_dataset(),
        solver=[system_message(system), generate()],
        scorer=[*deterministic_scorers(), grounding(judge)],
        metadata={"prompt_version": version},
    )


@task
def generate_copy_v1(judge: str | None = None) -> Task:
    """v1: same dataset and scorers, prompt rewritten against v0's failures."""
    return _copy_task(GEN_V1_TASK_NAME, GEN_V1_SYSTEM, GEN_V1, judge)
