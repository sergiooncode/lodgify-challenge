"""Explicit, injectable configuration.

Inspect resolves a dotenv file by walking up from the working directory looking
only for `.env`, so `.env.local` is never read and the file that *is* read
depends on where the process started. This module loads one explicit path
instead, and hands back a value object the rest of the code takes as an
argument (AGENTS.md §4, dependency injection).
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, replace
from pathlib import Path

from dotenv import dotenv_values

def find_repo_root(start: Path | None = None) -> Path:
    """Locate the repo by its `pyproject.toml` rather than by package depth.

    `parents[2]` of this file is only correct while the package sits in the
    source tree. It breaks the moment the package is copied or installed
    elsewhere — under a mutation-testing sandbox, or in site-packages for a
    non-editable install — and the failure is a confusing missing-fixture error
    rather than anything that names the real cause.
    """
    here = (start or Path(__file__)).resolve()
    for parent in here.parents:
        if (parent / "pyproject.toml").is_file():
            return parent
    return here.parents[2] if len(here.parents) > 2 else here.parent


REPO_ROOT = find_repo_root()
DEFAULT_ENV_FILE = REPO_ROOT / ".env.local"
DEFAULT_LOG_DIR = REPO_ROOT / "logs"

API_KEY_VAR = "ANTHROPIC_API_KEY"
ENV_FILE_VAR = "LODGIFY_ENV_FILE"

_DEFAULT = object()

GENERATOR_MODEL = "anthropic/claude-sonnet-5"
JUDGE_MODEL = "anthropic/claude-sonnet-5"


class MissingAPIKeyError(RuntimeError):
    """Raised only when a real model call is attempted without a key."""


@dataclass(frozen=True)
class Settings:
    anthropic_api_key: str | None = None
    generator_model: str = GENERATOR_MODEL
    judge_model: str = JUDGE_MODEL
    log_dir: Path = DEFAULT_LOG_DIR

    @property
    def has_api_key(self) -> bool:
        return bool(self.anthropic_api_key)

    def require_api_key(self) -> str:
        if not self.anthropic_api_key:
            raise MissingAPIKeyError(
                f"{API_KEY_VAR} is not set. Put it in {DEFAULT_ENV_FILE} or export it. "
                "Reading committed .eval logs never needs a key; only generating does."
            )
        return self.anthropic_api_key

    def export(self, environ: dict[str, str] | None = None) -> None:
        """Publish the key so the anthropic provider can read it.

        Explicit rather than a side effect of loading: nothing touches the
        process environment unless a caller asks for a real run.
        """
        target = os.environ if environ is None else environ
        target[API_KEY_VAR] = self.require_api_key()

    def with_models(self, *, generator: str | None = None, judge: str | None = None) -> Settings:
        return replace(
            self,
            generator_model=generator or self.generator_model,
            judge_model=judge or self.judge_model,
        )


def load_settings(
    env_file: Path | None | object = _DEFAULT,
    environ: Mapping[str, str] | None = None,
    **overrides: object,
) -> Settings:
    """Build Settings from one explicit file plus the process environment.

    An exported variable wins over the file. A missing file is not an error —
    the reviewer reproduces from committed logs with no key at all.

    `env_file` unset reads `LODGIFY_ENV_FILE` if present, else `.env.local`.
    That override is what lets the no-key gate run as a plain command instead of
    moving the author's env file out of the way. Passing `None` reads no file.
    """
    source = os.environ if environ is None else environ

    if env_file is _DEFAULT:
        override = source.get(ENV_FILE_VAR)
        env_file = Path(override) if override else DEFAULT_ENV_FILE

    values: dict[str, str] = {}
    if env_file is not None and Path(env_file).is_file():  # type: ignore[arg-type]
        values.update({k: v for k, v in dotenv_values(env_file).items() if v is not None})  # type: ignore[arg-type]

    if source.get(API_KEY_VAR):
        values[API_KEY_VAR] = source[API_KEY_VAR]

    key = values.get(API_KEY_VAR) or None
    return Settings(anthropic_api_key=key, **overrides)  # type: ignore[arg-type]
