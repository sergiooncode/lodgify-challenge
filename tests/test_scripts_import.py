"""Every script must at least import.

`scripts/` is otherwise untested — a broken import there surfaces only when
someone runs it, which during a refactor means finding out from the person you
handed it to.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

SCRIPTS = sorted((Path(__file__).resolve().parent.parent / "scripts").glob("*.py"))


def test_scripts_are_discovered() -> None:
    assert len(SCRIPTS) >= 5


@pytest.mark.parametrize("path", SCRIPTS, ids=lambda p: p.stem)
def test_script_imports(path: Path) -> None:
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec and spec.loader
    spec.loader.exec_module(importlib.util.module_from_spec(spec))
