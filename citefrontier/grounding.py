"""Claim-to-evidence checks used before a citation can be emitted."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Protocol

from .models import Evidence
from .text import normalized

# The optional Xet transfer client has repeatedly stalled in this Windows
# environment.  Standard HTTPS remains reproducible and is used only when a
# verifier checkpoint is not already local.
os.environ.setdefault("HF_HUB_DISABLE_XET", "1")


@dataclass(frozen=True)
class EntailmentResult:
    entailed: bool
    score: float
    label: str


class EntailmentVerifier(Protocol):
    """Minimal interface for a fixed claim-to-source verifier."""

    def verify(self, claim: str, evidence_text: str) -> EntailmentResult: ...


class ExtractiveEntailmentVerifier:
    """Dependency-free guard for the deterministic extractive prototype.

    The normal demo copies a selected source span verbatim into its claim. This
    verifier proves only that exact extractive case; deployments that paraphrase
    or generate claims must inject :class:`NliEntailmentVerifier` instead.
    """

    def verify(self, claim: str, evidence_text: str) -> EntailmentResult:
        compact_claim = normalized(claim)
        compact_evidence = normalized(evidence_text)
        entailed = bool(compact_claim) and compact_claim in compact_evidence
        return EntailmentResult(
            entailed=entailed,
            score=1.0 if entailed else 0.0,
            label="extractive_entailment" if entailed else "not_entailed",
        )


class NliEntailmentVerifier:
    """Fixed local NLI verifier for cited-evidence attribution.

    It intentionally evaluates only a proposed claim and a corpus chunk. It
    neither generates facts nor has access to benchmark labels.
    """

    def __init__(self, model_name: str = "cross-encoder/nli-MiniLM2-L6-H768", threshold: float = 0.70):
        if not 0 < threshold <= 1:
            raise ValueError("threshold must be in (0, 1]")
        try:
            import numpy as np
            from sentence_transformers import CrossEncoder
        except ImportError as exc:  # pragma: no cover - optional integration
            raise RuntimeError(
                "Install the retrieval extra: python -m pip install -e '.[retrieval]'"
            ) from exc
        self._np = np
        self._threshold = threshold
        self._model = CrossEncoder(model_name)
        labels = getattr(self._model.model.config, "id2label", {})
        self._labels = {int(index): str(label).lower() for index, label in labels.items()}
        self._entailment_index = next(
            (index for index, label in self._labels.items() if "entail" in label), None
        )
        if self._entailment_index is None:
            raise RuntimeError(f"NLI model {model_name} does not expose an entailment label")

    def verify(self, claim: str, evidence_text: str) -> EntailmentResult:
        logits = self._np.asarray(
            self._model.predict([(evidence_text, claim)], show_progress_bar=False), dtype=float
        )
        if logits.ndim == 2 and logits.shape[0] == 1:
            logits = logits[0]
        if logits.ndim != 1 or len(logits) != len(self._labels):
            raise RuntimeError("NLI model did not return one score per configured label")
        shifted = logits - logits.max()
        probabilities = self._np.exp(shifted) / self._np.exp(shifted).sum()
        score = float(probabilities[self._entailment_index])
        label_index = int(probabilities.argmax())
        return EntailmentResult(
            entailed=label_index == self._entailment_index and score >= self._threshold,
            score=score,
            label=self._labels[label_index],
        )


@dataclass(frozen=True)
class ClaimEvidenceSelection:
    """Result of selecting one support span from a post-rerank candidate set."""

    evidence: Evidence | None
    verification: EntailmentResult | None
    evaluated_candidate_ids: tuple[str, ...]


class ClaimEvidenceSelector:
    """Bind a proposed claim to one verified, retrieved evidence candidate.

    The selector intentionally receives only the current post-rerank
    candidates. It has no access to answer keys, historic assistant text, or
    corpus chunks outside that set.
    """

    def __init__(self, verifier: EntailmentVerifier | None = None):
        self._verifier = verifier or ExtractiveEntailmentVerifier()

    def select(self, claim: str, candidates: tuple[Evidence, ...]) -> ClaimEvidenceSelection:
        evaluated_ids = tuple(candidate.chunk.chunk_id for candidate in candidates)
        supported: list[tuple[int, Evidence, EntailmentResult]] = []
        for index, candidate in enumerate(candidates):
            result = self._verifier.verify(claim, candidate.chunk.text)
            if result.entailed:
                supported.append((index, candidate, result))
        if not supported:
            return ClaimEvidenceSelection(None, None, evaluated_ids)
        # Stable tie-break: preserve the rerank order when verifier scores tie.
        _, evidence, verification = max(supported, key=lambda item: (item[2].score, -item[0]))
        return ClaimEvidenceSelection(evidence, verification, evaluated_ids)


@dataclass(frozen=True)
class CitationGuardDecision:
    accepted_citation_ids: tuple[str, ...]
    rejected_citation_ids: tuple[str, ...]


class CitationCandidateGuard:
    """Strip every citation that did not originate in the current candidate set."""

    def enforce(
        self, proposed_citation_ids: tuple[str, ...], candidates: tuple[Evidence, ...]
    ) -> CitationGuardDecision:
        allowed = {candidate.chunk.chunk_id for candidate in candidates}
        accepted = tuple(citation for citation in proposed_citation_ids if citation in allowed)
        rejected = tuple(citation for citation in proposed_citation_ids if citation not in allowed)
        return CitationGuardDecision(accepted, rejected)
