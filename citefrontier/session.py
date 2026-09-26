"""Ephemeral answer and evidence state.

Only committed retrieval events may create citations. Provisional results are
kept for telemetry/readiness but never enter answer synthesis.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import uuid4

from .grounding import CitationCandidateGuard
from .models import AnswerVersion, Claim, Evidence, Intent
from .text import content_tokens, normalized


class CitationValidationError(ValueError):
    pass


@dataclass
class EphemeralSession:
    session_id: str = field(default_factory=lambda: str(uuid4()))
    provisional: dict[str, tuple[Evidence, ...]] = field(default_factory=dict)
    committed: dict[str, tuple[Evidence, ...]] = field(default_factory=dict)
    intent_by_key: dict[str, Intent] = field(default_factory=dict)
    versions: list[AnswerVersion] = field(default_factory=list)
    invalidated_provisionals: set[str] = field(default_factory=set)
    root_query: str = ""
    _committed_turn_intents: list[tuple[Intent, ...]] = field(default_factory=list)
    citation_guard: CitationCandidateGuard = field(default_factory=CitationCandidateGuard)

    @property
    def latest(self) -> AnswerVersion | None:
        return self.versions[-1] if self.versions else None

    @property
    def has_answer(self) -> bool:
        return self.latest is not None

    def stage_provisional(self, event_id: str, intent: Intent, evidence: tuple[Evidence, ...]) -> None:
        self.intent_by_key[intent.key] = intent
        self.provisional[event_id] = evidence

    def invalidate_provisionals(self) -> tuple[str, ...]:
        invalidated = tuple(self.provisional)
        self.invalidated_provisionals.update(invalidated)
        self.provisional.clear()
        return invalidated

    def commit(self, intent: Intent, evidence: tuple[Evidence, ...]) -> None:
        self.intent_by_key[intent.key] = intent
        self.committed[intent.key] = evidence

    def remember_committed_turn(self, intents: tuple[Intent, ...]) -> None:
        """Keep only recent user intent text for this in-memory session.

        Assistant output and provisional evidence are excluded.  This makes a
        follow-up query more searchable without treating dialogue history as
        independently citeable knowledge.
        """

        if intents:
            self._committed_turn_intents.append(intents)

    @staticmethod
    def _is_elliptical(query: str) -> bool:
        tokens = content_tokens(query)
        lower = normalized(query)
        return len(tokens) < 5 or lower.startswith(
            (
                "what about",
                "what does that",
                "what does it",
                "and what",
                "how about",
                "is that",
                "yes",
                "no",
                "i do not",
                "i dont",
            )
        )

    def contextualize(self, intent: Intent, max_prior_turns: int = 1) -> tuple[str, tuple[str, ...]]:
        """Return a retrieval-only query sidecar for an elliptical follow-up.

        No model rewrites the user text and no historical answer is copied into
        the query.  The returned intent keys are solely for traceability.
        """

        if not self._is_elliptical(intent.query) or not self._committed_turn_intents:
            return intent.query, ()
        prior_turns = self._committed_turn_intents[-max_prior_turns:]
        prior_intents = tuple(intent for turn in prior_turns for intent in turn)
        if not prior_intents:
            return intent.query, ()
        context = " ".join(prior.query for prior in prior_intents)
        lower = normalized(intent.query)
        deictic = lower.startswith(
            (
                "what about",
                "about that",
                "what does that",
                "what does it",
                "yes",
                "no",
                "i do not",
                "i dont",
            )
        )
        # A pure follow-up phrase contributes no topic terms. Reuse the last
        # user intent instead of diluting its retrieval signal. More specific
        # short questions retain their wording as a sidecar.
        return (context if deictic else f"{intent.query} {context}"), tuple(prior.key for prior in prior_intents)

    def _claim_for(self, intent_key: str, evidence: tuple[Evidence, ...], claim_id: str) -> Claim:
        valid = tuple(item for item in evidence if item.retrieval_event_id not in self.invalidated_provisionals)
        if not valid:
            return Claim(
                claim_id=claim_id,
                intent_key=intent_key,
                text=f"I could not verify: {self.intent_by_key[intent_key].query}.",
                citations=(),
                evidence_event_ids=(),
            )
        top = valid[0]
        guard = self.citation_guard.enforce((top.chunk.chunk_id,), valid)
        citations = guard.accepted_citation_ids
        if not citations:
            return Claim(
                claim_id=claim_id,
                intent_key=intent_key,
                text=f"I could not verify: {self.intent_by_key[intent_key].query}.",
                citations=(),
                evidence_event_ids=(),
            )
        known = {item.chunk.chunk_id for group in self.committed.values() for item in group}
        if not set(citations).issubset(known):
            raise CitationValidationError("A claim attempted to cite non-committed corpus evidence")
        return Claim(
            claim_id=claim_id,
            intent_key=intent_key,
            text=top.chunk.text,
            citations=citations,
            evidence_event_ids=(top.retrieval_event_id,),
        )

    def synthesize_initial(self, root_query: str) -> AnswerVersion:
        self.root_query = root_query
        claims = tuple(
            self._claim_for(intent_key, evidence, f"claim-{index + 1}")
            for index, (intent_key, evidence) in enumerate(sorted(self.committed.items()))
        )
        version = AnswerVersion(
            version=self.latest.version + 1 if self.latest else 1,
            parent_version=self.latest.version if self.latest else None,
            claims=claims,
            changed_claim_ids=tuple(claim.claim_id for claim in claims),
        )
        self.versions.append(version)
        return version

    def refine(self, target_intent_key: str, delta_intent: Intent, evidence: tuple[Evidence, ...]) -> AnswerVersion:
        if not self.latest:
            raise ValueError("Cannot refine a session without an answer")
        self.intent_by_key[delta_intent.key] = delta_intent
        self.committed[delta_intent.key] = evidence
        updated: list[Claim] = []
        changed: list[str] = []
        for claim in self.latest.claims:
            if claim.intent_key != target_intent_key:
                updated.append(claim)
                continue
            replacement_id = f"{claim.claim_id}-v{self.latest.version + 1}"
            updated.append(self._claim_for(delta_intent.key, evidence, replacement_id))
            changed.append(replacement_id)
        version = AnswerVersion(
            version=self.latest.version + 1,
            parent_version=self.latest.version,
            claims=tuple(updated),
            changed_claim_ids=tuple(changed),
        )
        self.versions.append(version)
        return version
