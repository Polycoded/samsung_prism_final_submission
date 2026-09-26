"""End-to-end orchestration of the validation mechanisms."""

from __future__ import annotations

from itertools import count
from concurrent.futures import ThreadPoolExecutor

from .controller import RetrievalController
from .grounding import CitationCandidateGuard, ClaimEvidenceSelector
from .models import ControllerAction, Decision, EngineOutput, Intent, TranscriptEvent
from .retrieval import HybridRetriever
from .session import EphemeralSession
from .telemetry import TelemetryRecorder


class CiteFrontierEngine:
    def __init__(
        self,
        retriever: HybridRetriever,
        telemetry: TelemetryRecorder | None = None,
        use_dialogue_context: bool = False,
        claim_evidence_selector: ClaimEvidenceSelector | None = None,
    ):
        self.retriever = retriever
        self.telemetry = telemetry or TelemetryRecorder()
        self._use_dialogue_context = use_dialogue_context
        self._claim_evidence_selector = claim_evidence_selector or ClaimEvidenceSelector()
        self._citation_guard = CitationCandidateGuard()
        self._controllers: dict[str, RetrievalController] = {}
        self._event_counter = count(1)

    def new_session(self) -> EphemeralSession:
        session = EphemeralSession(citation_guard=self._citation_guard)
        self._controllers[session.session_id] = RetrievalController()
        return session

    def begin_turn(self, session: EphemeralSession) -> None:
        """Reset ASR-prefix stability state while retaining ephemeral context.

        Call this when a new user speech turn begins. It never creates a new
        persistent session and leaves corpus evidence unchanged.
        """

        self._controllers[session.session_id] = RetrievalController()

    def _retrieval_id(self) -> str:
        return f"retrieval-{next(self._event_counter)}"

    def _retrieve(self, session: EphemeralSession, intent: Intent, timestamp_s: float, trigger: str) -> tuple[str, tuple]:
        retrieval_id = self._retrieval_id()
        search_query, context_intent_keys = (
            session.contextualize(intent) if self._use_dialogue_context else (intent.query, ())
        )
        evidence = self.retriever.search(search_query, retrieval_id)
        self.telemetry.record(
            "retrieval_started",
            timestamp_s,
            session.session_id,
            retrieval_event_id=retrieval_id,
            trigger=trigger,
            query=search_query,
            user_query=intent.query,
            contextualization_used=bool(context_intent_keys),
            context_intent_keys=list(context_intent_keys),
            candidate_chunk_ids=[item.chunk.chunk_id for item in evidence],
            coverage=[round(item.coverage, 3) for item in evidence],
            graph_expanded=any(item.origin == "graph_one_hop" for item in evidence),
        )
        return retrieval_id, evidence

    def _select_claim_evidence(
        self,
        session: EphemeralSession,
        retrieval_id: str,
        evidence: tuple,
        timestamp_s: float,
    ) -> tuple:
        """Select verified evidence after reranking and before synthesis.

        The provisional pipeline never calls this method: only endpoint and
        delta retrieval results can become answer citations.
        """

        draft_claim = evidence[0].chunk.text if evidence else ""
        selection = self._claim_evidence_selector.select(draft_claim, evidence)
        proposed = (selection.evidence.chunk.chunk_id,) if selection.evidence else ()
        guard = self._citation_guard.enforce(proposed, evidence)
        selected = (
            (selection.evidence,)
            if selection.evidence and guard.accepted_citation_ids
            else ()
        )
        self.telemetry.record(
            "claim_evidence_selected",
            timestamp_s,
            session.session_id,
            retrieval_event_id=retrieval_id,
            candidate_chunk_ids=list(selection.evaluated_candidate_ids),
            selected_chunk_id=(selected[0].chunk.chunk_id if selected else None),
            verification_score=(selection.verification.score if selection.verification else None),
            verification_label=(selection.verification.label if selection.verification else None),
            rejected_citation_ids=list(guard.rejected_citation_ids),
            uncertainty_required=not bool(selected),
        )
        return selected

    def process_stream(self, session: EphemeralSession, event: TranscriptEvent) -> EngineOutput:
        controller = self._controllers[session.session_id]
        action = controller.decide(event, has_answer=session.has_answer)
        self.telemetry.record(
            "controller_decision",
            event.timestamp_s,
            session.session_id,
            decision=action.decision.value,
            reason=action.reason,
            intents=[intent.query for intent in action.intents],
            token_cost_estimate=0,
        )

        if action.invalidates_provisional:
            invalidated = session.invalidate_provisionals()
            self.telemetry.record(
                "provisional_invalidated",
                event.timestamp_s,
                session.session_id,
                retrieval_event_ids=list(invalidated),
            )

        if action.decision is Decision.SUPPRESS:
            latest = session.latest
            rendered = latest.render(bullets=True) if latest else None
            return EngineOutput(action, latest, rendered, ())

        retrieval_ids: list[str] = []
        if action.decision is Decision.PROVISIONAL_RETRIEVE:
            for intent in action.intents:
                retrieval_id, evidence = self._retrieve(session, intent, event.timestamp_s, "provisional")
                session.stage_provisional(retrieval_id, intent, evidence)
                retrieval_ids.append(retrieval_id)
            return EngineOutput(action, session.latest, None, tuple(retrieval_ids))

        if action.decision is Decision.COMMIT_RETRIEVE:
            # A new factual turn cannot accidentally re-emit previous candidates.
            session.committed.clear()
            with ThreadPoolExecutor(max_workers=min(4, max(1, len(action.intents)))) as pool:
                results = list(pool.map(
                    lambda intent: self._retrieve(session, intent, event.timestamp_s, "endpoint_commit"),
                    action.intents,
                ))
            for intent, (retrieval_id, evidence) in zip(action.intents, results):
                session.commit(
                    intent,
                    self._select_claim_evidence(session, retrieval_id, evidence, event.timestamp_s),
                )
                retrieval_ids.append(retrieval_id)
            answer = session.synthesize_initial(event.text)
            session.remember_committed_turn(action.intents)
            self.telemetry.record(
                "answer_version",
                event.timestamp_s,
                session.session_id,
                version=answer.version,
                parent_version=answer.parent_version,
                changed_claim_ids=list(answer.changed_claim_ids),
                citations=[citation for claim in answer.claims for citation in claim.citations],
            )
            return EngineOutput(action, answer, answer.render(), tuple(retrieval_ids))

        return EngineOutput(action, session.latest, None, ())

    def refine_with_late_detail(
        self,
        session: EphemeralSession,
        timestamp_s: float,
        target_intent_key: str,
        late_detail: str,
    ) -> EngineOutput:
        target = session.intent_by_key[target_intent_key]
        delta_intent = Intent(
            key=f"{target.key}-delta-v{(session.latest.version if session.latest else 0) + 1}",
            query=f"{target.query} {late_detail}",
        )
        action = ControllerAction(
            decision=Decision.COMMIT_RETRIEVE,
            intents=(delta_intent,),
            reason="late_detail_targeted_delta",
        )
        self.telemetry.record(
            "controller_decision",
            timestamp_s,
            session.session_id,
            decision=action.decision.value,
            reason=action.reason,
            intents=[delta_intent.query],
            token_cost_estimate=0,
        )
        retrieval_id, evidence = self._retrieve(session, delta_intent, timestamp_s, "late_detail_delta")
        answer = session.refine(
            target_intent_key,
            delta_intent,
            self._select_claim_evidence(session, retrieval_id, evidence, timestamp_s),
        )
        self.telemetry.record(
            "answer_version",
            timestamp_s,
            session.session_id,
            version=answer.version,
            parent_version=answer.parent_version,
            changed_claim_ids=list(answer.changed_claim_ids),
            citations=[citation for claim in answer.claims for citation in claim.citations],
        )
        return EngineOutput(action, answer, answer.render(), (retrieval_id,))
