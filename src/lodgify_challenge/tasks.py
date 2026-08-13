"""Minimal Task used to settle PLAN Phase 0.

The brief's reproducibility requirement rests entirely on a committed `.eval` log
re-opening with no API call. This proves the mechanism before any scorer is
written, so the whole design isn't built on an assumption about log replay.
"""

from inspect_ai import Task, task
from inspect_ai.dataset import Sample
from inspect_ai.scorer import includes
from inspect_ai.solver import generate, system_message

from lodgify_challenge.dataset import property_dataset
from lodgify_challenge.prompts import GEN_V0, GEN_V0_SYSTEM
from lodgify_challenge.scorers import deterministic_scorers, grounding

PROBE_TOKEN = "PROBE-OK"
GEN_V0_TASK_NAME = f"generate_copy_{GEN_V0}"


@task
def replay_probe() -> Task:
    return Task(
        dataset=[Sample(input=f"Reply with exactly: {PROBE_TOKEN}", target=PROBE_TOKEN)],
        solver=generate(),
        scorer=includes(),
    )


@task
def generate_copy_v0(judge: str | None = None) -> Task:
    """One property → generated copy → one deterministic score.

    The prompt version is carried in task metadata so a log identifies which
    wording produced it. Generator versions are separate named tasks rather than
    a parameter, so results never blur together across versions.
    """
    return Task(
        name=GEN_V0_TASK_NAME,
        dataset=property_dataset(),
        solver=[system_message(GEN_V0_SYSTEM), generate()],
        scorer=[*deterministic_scorers(), grounding(judge)],
        metadata={"prompt_version": GEN_V0},
    )
