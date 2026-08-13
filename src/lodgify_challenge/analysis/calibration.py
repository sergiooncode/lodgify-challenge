"""Judge calibration: how far the grounding verdicts can be trusted.

Two numbers, and they answer different questions:

- **Agreement** with human labels is *bias* — does the judge systematically call
  things differently from a person?
- **Self-consistency** across repeats is *variance* — does it call the same claim
  the same way twice?

A judge can be perfectly consistent and consistently wrong, or unbiased on
average and wildly unstable. Reporting one without the other says almost
nothing, so both are reported together.

Labels join to generations by a hash of the generation text, never by sample id:
generation is uncached, so a re-run would silently attach labels to different
copy (AGENTS §6).
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Hashable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from lodgify_challenge.eval.grounding import Verdict

TODO = "TODO(human)"


def generation_hash(text: str) -> str:
    """Stable identity for one generation."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class LabelRecord:
    generation_sha256: str
    claim: str
    verdict: Verdict
    note: str = ""

    @classmethod
    def parse(cls, line: str) -> LabelRecord | None:
        """Parse one JSONL line, skipping blanks and unlabelled rows.

        A row still carrying the TODO marker is not an error — it is simply not
        labelled yet, and counting it would quietly corrupt agreement.
        """
        line = line.strip()
        if not line or line.startswith("#"):
            return None
        data = json.loads(line)
        raw = str(data.get("verdict", "")).strip()
        if not raw or raw == TODO:
            return None
        return cls(
            generation_sha256=str(data["generation_sha256"]),
            claim=str(data["claim"]),
            verdict=Verdict.parse(raw),
            note=str(data.get("note", "")),
        )


def load_labels(path: Path) -> list[LabelRecord]:
    if not path.is_file():
        return []
    return [r for r in (LabelRecord.parse(l) for l in path.read_text().splitlines()) if r]


def raw_agreement(pairs: Sequence[tuple[Hashable, Hashable]]) -> float:
    """Share of items where both raters chose the same label."""
    if not pairs:
        return 0.0
    return sum(1 for a, b in pairs if a == b) / len(pairs)


def cohens_kappa(pairs: Sequence[tuple[Hashable, Hashable]]) -> float:
    """Agreement corrected for chance.

    Raw agreement flatters a rater on a skewed distribution: if almost
    everything is one label, always answering that label scores well while
    measuring nothing. Kappa subtracts the agreement two random raters with
    these marginals would reach anyway.

    Returns 0.0 when chance agreement is already perfect — the degenerate case
    where kappa is undefined rather than good.

    Label-agnostic on purpose: the verdict labels and the binary coverage ticks
    are different vocabularies but the same arithmetic.
    """
    if not pairs:
        return 0.0
    n = len(pairs)
    first = Counter(a for a, _ in pairs)
    second = Counter(b for _, b in pairs)
    expected = sum(first[k] * second[k] for k in set(first) | set(second)) / (n**2)
    if expected >= 1.0:
        return 0.0
    return (raw_agreement(pairs) - expected) / (1 - expected)


@dataclass(frozen=True)
class Agreement:
    """Judge verdicts against human labels, on the claims both cover."""

    pairs: list[tuple[Verdict, Verdict]]
    """(human, judge) for each matched claim."""

    unmatched_labels: int = 0

    claims: list[str] = field(default_factory=list)
    """Claim text per pair, same order. A disagreement count is not actionable;
    the claim that caused it is."""

    notes: list[str] = field(default_factory=list)
    """The labeller's reasoning per pair, same order."""

    @property
    def n(self) -> int:
        return len(self.pairs)

    @property
    def raw(self) -> float:
        return raw_agreement(self.pairs)

    @property
    def kappa(self) -> float:
        return cohens_kappa(self.pairs)

    def confusion(self) -> dict[tuple[Verdict, Verdict], int]:
        return dict(Counter(self.pairs))

    def disagreements(self) -> list[tuple[Verdict, Verdict]]:
        return [(h, j) for h, j in self.pairs if h is not j]

    def disagreement_detail(self) -> list[tuple[str, Verdict, Verdict, str]]:
        """(claim, human, judge, note) for every mismatch."""
        out = []
        for i, (human, judge) in enumerate(self.pairs):
            if human is not judge:
                claim = self.claims[i] if i < len(self.claims) else ""
                note = self.notes[i] if i < len(self.notes) else ""
                out.append((claim, human, judge, note))
        return out


def compare(
    labels: list[LabelRecord], judged: dict[tuple[str, str], Verdict]
) -> Agreement:
    """Match labels to judge verdicts by (generation hash, claim text).

    Labels with no matching judge verdict are counted, not dropped silently: a
    label that matches nothing usually means the run was re-generated and the
    hash moved, which is the exact failure the hash join exists to make loud.
    """
    pairs: list[tuple[Verdict, Verdict]] = []
    claims: list[str] = []
    notes: list[str] = []
    unmatched = 0
    for label in labels:
        key = (label.generation_sha256, label.claim)
        if key in judged:
            pairs.append((label.verdict, judged[key]))
            claims.append(label.claim)
            notes.append(label.note)
        else:
            unmatched += 1
    return Agreement(
        pairs=pairs, unmatched_labels=unmatched, claims=claims, notes=notes
    )


@dataclass(frozen=True)
class SelfConsistency:
    """Judge against itself across repeated passes over the same generations."""

    per_claim: dict[str, list[Verdict]]

    @property
    def n(self) -> int:
        return len(self.per_claim)

    @property
    def repeats(self) -> int:
        return max((len(v) for v in self.per_claim.values()), default=0)

    @property
    def stable_share(self) -> float:
        """Share of claims that got the same verdict every time."""
        if not self.per_claim:
            return 0.0
        stable = sum(1 for v in self.per_claim.values() if len(set(v)) == 1)
        return stable / self.n

    def unstable(self) -> dict[str, list[Verdict]]:
        return {c: v for c, v in self.per_claim.items() if len(set(v)) > 1}


def self_consistency(passes: list[dict[str, Verdict]]) -> SelfConsistency:
    """Collect repeated verdicts per claim.

    Only claims seen in every pass are counted. A claim the extractor produced
    in one pass but not another is a different instability — worth knowing, but
    not the same measurement, and averaging them together would blur both.
    """
    if not passes:
        return SelfConsistency({})
    shared = set(passes[0])
    for p in passes[1:]:
        shared &= set(p)
    return SelfConsistency({c: [p[c] for p in passes] for c in sorted(shared)})
