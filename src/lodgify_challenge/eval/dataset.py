"""Fixtures → Inspect Dataset.

The canonical listing rides along in `Sample.metadata` so scorers can check
generated claims against the exact input the model saw, rather than re-reading
and re-adapting the fixture.
"""

from __future__ import annotations

from pathlib import Path

from inspect_ai.dataset import MemoryDataset, Sample

from lodgify_challenge.domain.adapters import listing_from_json
from lodgify_challenge.config import REPO_ROOT
from lodgify_challenge.domain.prompts import render_listing

FIXTURE_DIR = REPO_ROOT / "data" / "fixtures"

ADVERSARIAL: frozenset[str] = frozenset(
    {"apartment_porto_sparse", "cottage_injection", "absurd_values"}
)
"""Which fixtures form the adversarial slice.

Phase 7 reports adversarial and realistic separately, so the split has to be
recorded at dataset-build time rather than reconstructed from results later.
"""


def property_samples(fixture_dir: Path | None = None) -> list[Sample]:
    directory = fixture_dir or FIXTURE_DIR
    samples = []
    for path in sorted(directory.glob("*.json")):
        listing = listing_from_json(path.read_text())
        samples.append(
            Sample(
                id=path.stem,
                input=render_listing(listing),
                metadata={
                    "fixture": path.stem,
                    "slice": "adversarial" if path.stem in ADVERSARIAL else "realistic",
                    "listing": listing.model_dump(),
                },
            )
        )
    return samples


def property_dataset(fixture_dir: Path | None = None) -> MemoryDataset:
    return MemoryDataset(property_samples(fixture_dir))
