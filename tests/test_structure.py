"""Structural rules the package layout is supposed to express.

Folders alone enforce nothing. `domain/` is meant to be the part that could ship
in a product; `eval/` and `analysis/` are the harness that measures it. If the
domain layer starts importing the harness, that distinction is decoration and the
README's claim about it becomes false.

Also covers the generated notebook, which no other test touches: it is built by a
script and executed by a make target, so a malformed cell would otherwise surface
only when someone runs it.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PACKAGE = ROOT / "src" / "lodgify_challenge"
NOTEBOOK = ROOT / "evals.ipynb"

LAYERS = ("domain", "eval", "analysis")

FORBIDDEN: dict[str, tuple[str, ...]] = {
    # The product layer must not depend on the thing that measures it.
    "domain": ("eval", "analysis"),
}


def imported_layers(path: Path) -> set[str]:
    found: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text())):
        names = []
        if isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module)
        elif isinstance(node, ast.Import):
            names += [a.name for a in node.names]
        for name in names:
            parts = name.split(".")
            if parts[:1] == ["lodgify_challenge"] and len(parts) > 1 and parts[1] in LAYERS:
                found.add(parts[1])
    return found


def modules_in(layer: str) -> list[Path]:
    return sorted((PACKAGE / layer).rglob("*.py"))


def test_every_layer_exists_and_has_modules() -> None:
    for layer in LAYERS:
        assert modules_in(layer), f"{layer} has no modules — did a move go wrong?"


@pytest.mark.parametrize("layer", sorted(FORBIDDEN))
def test_layer_does_not_import_upward(layer: str) -> None:
    offenders = {}
    for path in modules_in(layer):
        leaked = imported_layers(path) & set(FORBIDDEN[layer])
        if leaked:
            offenders[path.name] = sorted(leaked)
    assert not offenders, f"{layer}/ must not import {FORBIDDEN[layer]}: {offenders}"


def test_nothing_in_the_package_imports_scripts() -> None:
    """`scripts/` is operator tooling. A module importing it would make the
    library depend on the command line."""
    offenders = [
        path.name
        for path in PACKAGE.rglob("*.py")
        for node in ast.walk(ast.parse(path.read_text()))
        if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("scripts")
    ]
    assert not offenders


# --- the generated notebook --------------------------------------------------


def test_notebook_is_valid_and_has_content() -> None:
    nb = json.loads(NOTEBOOK.read_text())
    assert nb["nbformat"] == 4
    assert len(nb["cells"]) >= 20


@pytest.mark.parametrize(
    "index",
    range(len(json.loads(NOTEBOOK.read_text())["cells"])),
)
def test_notebook_code_cells_are_syntactically_valid(index: int) -> None:
    """Catches a malformed cell without executing the notebook.

    It will not catch a runtime error — a cell using a name imported in a later
    cell compiles fine and fails on execution. That gap is covered by
    `make notebook`, which executes the whole thing offline.
    """
    cell = json.loads(NOTEBOOK.read_text())["cells"][index]
    if cell["cell_type"] != "code":
        pytest.skip("markdown")
    compile("".join(cell["source"]), f"cell-{index}", "exec")


def test_notebook_outputs_were_produced_without_a_key() -> None:
    """The committed outputs must show the reviewer's environment.

    Executing with a key present would bake "API key: present" into the
    notebook and quietly undercut the reproducibility claim.
    """
    text = "".join(
        "".join(o.get("text", []))
        for cell in json.loads(NOTEBOOK.read_text())["cells"]
        if cell["cell_type"] == "code"
        for o in cell.get("outputs", [])
    )
    assert "API key   : absent" in text, "notebook was executed with a key present"
