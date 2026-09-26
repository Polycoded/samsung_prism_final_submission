"""Revision-safe streaming with ephemeral, claim-scoped evidence."""
from __future__ import annotations
import asyncio
import hashlib
import json
import os
import re
import secrets
import time
from dataclasses import asdict
from pathlib import Path
from uuid import uuid4
from citefrontier.models import CorpusChunk
from citefrontier.grounding import ExtractiveEntailmentVerifier
from .decomposition import Decomposer, presentation, presentation_prefix, translation_request, social, terms
from .search import SearchIndex
from .transcript import normalize_correction, normalize_disfluencies


class LiveRuntime:
    def __init__(self, chunks=None, backend=None, parser=None, reuse=True, rerank=True):
        if chunks is None:
            path = Path(os.environ.get("CITEFRONTIER_CORPUS", Path(__file__).parent / "corpus.json"))
            chunks = tuple(CorpusChunk(**item) for item in json.loads(path.read_text(encoding="utf-8")))
        if not chunks or len({c.chunk_id for c in chunks}) != len(chunks):
            raise ValueError("Corpus requires nonempty, unique chunk IDs")
        for c in chunks:
            if not all([c.doc_id, c.section, c.text.strip()]):
                raise ValueError("Every chunk requires source identity and text")
            if c.metadata.get("end") and int(c.metadata["end"]) - int(c.metadata.get("start", 0)) != len(c.text):
                raise ValueError("Passage offsets do not match source length")
        self.chunks = chunks
        self.corpus_hash = hashlib.sha256(json.dumps([asdict(c) for c in chunks], sort_keys=True).encode()).hexdigest()
        self.backend = backend or os.environ.get("CITEFRONTIER_BACKEND", "lightweight")
        parser_mode = parser or os.environ.get("CITEFRONTIER_PARSER", "spacy")
        if parser_mode in {"bert", "shadow", "auto"}:
            from .bert_decomposition import HybridDecomposer
            self.decomposer = HybridDecomposer(
                chunks, parser_mode,
                fallback_parser=os.environ.get("CITEFRONTIER_FALLBACK_PARSER", "spacy"),
                model_path=os.environ.get("CITEFRONTIER_BERT_MODEL"),
                threshold=float(os.environ.get("CITEFRONTIER_BERT_THRESHOLD", ".90")),
            )
            if os.environ.get("CITEFRONTIER_BERT_PRELOAD", "1") == "1":
                try:
                    self.decomposer.detector._load()
                except Exception:
                    # Prediction records the concrete local load error and the
                    # hybrid path serves the unchanged fallback splitter.
                    pass
        else:
            self.decomposer = Decomposer(chunks, parser_mode)
        self.retriever = SearchIndex(chunks, self.decomposer, self.backend, rerank)
        self.reuse = reuse
        self.work_slots = asyncio.Semaphore(4)

    def connection(self):
        return LiveConnection(self)


class LiveConnection:
    def __init__(self, runtime):
        self.runtime = runtime
        self.session_id = str(uuid4())
        self.token = secrets.token_urlsafe(32)
        self.lock = asyncio.Lock()
        self.generation = 0
        self.turn_id = None
        self.turns, self.events, self.receipts, self.inflight, self.cache = {}, {}, {}, {}, {}
        self.claims, self.history, self.telemetry = [], [], []
        self.intents = {}
        self.version = 0
        self.previous, self.previous_text = (), ""
        self.closed = False
        self.origin = time.perf_counter()
        self.search_count = self.reuse_count = 0
        self.verifier = ExtractiveEntailmentVerifier()

    def record(self, kind, event, **payload):
        item = {"event_type": kind, "timestamp_s": event.timestamp_ms / 1000,
                "server_ms": round((time.perf_counter() - self.origin) * 1000, 3),
                "session_id": self.session_id, "event_id": event.event_id,
                "turn_id": event.turn_id,
                # The prototype is deliberately non-generative. Recording an
                # explicit zero keeps cost telemetry complete rather than
                # leaving an ambiguous missing value.
                "token_cost": {"input_tokens": 0, "output_tokens": 0,
                               "estimated_usd": 0.0, "basis": "non_generative_pipeline"},
                "payload": payload}
        if not self.closed:
            self.telemetry.append(item)
        return item

    def _cache_key(self, intent):
        return (self.runtime.corpus_hash, self.runtime.backend, intent.key)

    def _snapshot(self, event, decision, reason, trace, intents=(), changed=(), answer=False, clarification=None):
        claims = list(self.claims) if answer else []
        presentation_items = []
        if decision == 'suppress' and claims and re.search(r'\bbullets\b',event.text,re.I):
            count = re.search(r'\b(one|two|three|four|five|\d+)\s+bullets\b',event.text,re.I)
            names = {'one':1,'two':2,'three':3,'four':4,'five':5}
            requested = (names.get(count[1].lower()) or int(count[1])) if count else len(claims)
            count = min(len(claims),max(1,requested))
            for index in range(count):
                group = claims[index*len(claims)//count:(index+1)*len(claims)//count]
                presentation_items.append({'claim_ids':[c['claim_id'] for c in group],
                                           'text':' '.join(c['text'] for c in group),
                                           'citations':[ref for c in group for ref in c['citations']]})
        return {"type": "update", "session_id": self.session_id, "turn_id": event.turn_id,
                "event_id": event.event_id, "decision": decision, "reason": reason,
                "sub_queries": [i.public() for i in intents], "claims": claims,
                "answer": ('\n'.join('- '+item['text'] for item in presentation_items) if presentation_items else "\n".join(c["text"] for c in claims)) if answer else None,
                "presentation_items": presentation_items,
                "answer_version": self.version, "changed_claim_ids": list(changed),
                "citations": [citation for c in claims for citation in c["citations"]],
                "uncertainty": [c["text"] for c in claims if not c["citations"]],
                "clarification": clarification, "tentative_count": sum(len(v) for v in self.cache.values()),
                "retrieval_events": trace, "latency_ms": 0,
                "stats": {"searches": self.search_count, "cache_reuses": self.reuse_count},
                "history": list(self.history[-10:]), "corpus_hash": self.runtime.corpus_hash}

    def _refinement(self, text, target=None):
        if not self.claims:
            if target:
                raise ValueError("No answer exists to refine")
            return None, None
        active = {c["intent_key"]: c for c in self.claims}
        if target and target not in active:
            raise ValueError("Refinement target is not in the current answer")
        entities = self.runtime.decomposer.entities(text)
        is_delta = bool(target or re.match(r"\s*(?:actually|instead|what about|how about|change|make (?:it|that)|for (?:the )?\w+[, ]+what about)\b", text, re.I))
        if not is_delta:
            return None, None
        prior = [self.intents[k] for k in active]
        selected = [self.intents[target]] if target else []
        entity_change = len(entities) == 1 and bool(re.search(r"\b(?:instead|actually|change)\b", text, re.I))
        if not selected and entity_change and len({e for i in prior for e in i.entity_ids}) == 1:
            selected = prior
        if not selected:
            topic = self.runtime.decomposer.topic(text, entities)
            # Fronted property is an explicit refinement target, even when a
            # source-specific qualifier is new to the original intent.
            front = re.match(r"\s*for\s+(?:the\s+)?([^,]+),", text, re.I)
            if front:
                topic = terms(front[1])
            scores = [(len(topic & set(i.topic)), i) for i in prior]
            best = max((score for score, _ in scores), default=0)
            matches = [i for score, i in scores if score == best and score > 0]
            if len(matches) == 1:
                selected = matches
        if not selected:
            return {}, "Which part should change? Select ‘Refine this claim’ or name the property, such as warranty or repair."
        updates = {}
        for old in selected:
            if entity_change and len(old.entity_ids) == 1:
                query = re.sub(re.escape(self.runtime.decomposer.aliases[old.entity_ids[0]]), self.runtime.decomposer.aliases[entities[0]], old.query, flags=re.I)
            else:
                detail = re.sub(r"^\s*for\s+[^,]+,\s*", "", text, flags=re.I)
                detail = re.sub(r"^\s*(?:what about|how about|actually)\s*", "", detail, flags=re.I)
                query = old.query.rstrip("? .") + " " + detail
                number = re.search(r"\b(\d+)\s+(people|attendees|days|months|years)\b", text, re.I)
                if number:
                    query = re.sub(r"\b\d+\s+" + re.escape(number[2]) + r"\b", number[0], old.query, flags=re.I)
                    if query == old.query:
                        query += " " + number[0]
            parsed = self.runtime.decomposer.split(query)
            if len(parsed) != 1:
                return {}, "That update introduces multiple requests. Refine one claim at a time or ask a new compound question."
            updates[old.key] = parsed[0]
        return updates, None

    def _late_detail_additions(self, text):
        """Turn a declarative follow-up into scoped delta intents.

        This is deliberately conservative: it requires an existing answer, a
        referential opening, one prior entity, and meaningful overlap with the
        prior request. It therefore does not reinterpret an ordinary new
        question as an in-place refinement.
        """
        if not self.claims or not re.match(r"\s*(?:the|this|that|it|they|their)\b", text, re.I):
            return ()
        if re.search(r"\b(?:what|when|where|how|which|who|tell|show|find|list)\b", text, re.I):
            return ()
        active = [self.intents[c["intent_key"]] for c in self.claims if c["intent_key"] in self.intents]
        entity_ids = {e for intent in active for e in intent.entity_ids}
        prior_topics = set().union(*(set(intent.topic) for intent in active)) if active else set()
        if len(entity_ids) != 1 or not (terms(text) & prior_topics):
            return ()
        entity = next(iter(entity_ids))
        subject = self.runtime.decomposer.aliases[entity]
        clauses = [part.strip(" ,;?.") for part in re.split(r"\s*(?:;|\band\b)\s*", text, flags=re.I)]
        clauses = [part for part in clauses if len(terms(part)) >= 2]
        if not clauses:
            return ()
        additions = []
        for clause in clauses:
            parsed = self.runtime.decomposer.split(f"{subject} {clause}")
            if len(parsed) != 1:
                return ()
            additions.append(parsed[0])
        return tuple(additions)

    async def _retrieve(self, event, intent, final):
        trace = []
        retrieval_id = f"r-{event.event_id}-{intent.key[:8]}"
        cached = self.cache.get(self._cache_key(intent)) if final and self.runtime.reuse else None
        if cached is not None:
            self.reuse_count += 1
            ids = cached
            trace.append(self.record("candidate_cache_reused", event, retrieval_event_id=retrieval_id,
                                     query=intent.query, candidate_chunk_ids=list(ids), phase="final_candidate"))
        else:
            self.search_count += 1
            trace.append(self.record("retrieval_started", event, retrieval_event_id=retrieval_id,
                                     query=intent.query, intent_id=intent.key, trigger="final_commit" if final else "tentative"))
            async with self.runtime.work_slots:
                ids = await asyncio.to_thread(self.runtime.retriever.candidates, intent)
            trace.append(self.record("retrieval_finished", event, retrieval_event_id=retrieval_id,
                                     intent_id=intent.key, candidate_chunk_ids=list(ids), phase="tentative" if not final else "final_candidate"))
        evidence = ()
        if final:
            async with self.runtime.work_slots:
                evidence = await asyncio.to_thread(self.runtime.retriever.finalize, intent, ids)
            trace.append(self.record("final_evidence_ranked", event, retrieval_event_id=retrieval_id,
                                     intent_id=intent.key, candidate_chunk_ids=[c.evidence_id for c in evidence],
                                     query=intent.query, reranked=self.runtime.retriever.rerank_enabled))
        return intent, ids, evidence, retrieval_id, trace

    def _claim(self, intent, candidates, retrieval_id, event, previous=None):
        candidate_ids = {c.evidence_id for c in candidates}
        evidence = []
        conflict = False
        if candidates:
            choice = candidates[0]
            chunk = self.runtime.retriever.chunks[choice.evidence_id]
            quantities = set(re.findall(r"\b(\d+)[ -](months?|years?|days?|people)\b", chunk.text, re.I))
            for other in candidates[1:]:
                alternative = self.runtime.retriever.chunks[other.evidence_id]
                competing = set(re.findall(r"\b(\d+)[ -](months?|years?|days?|people)\b", alternative.text, re.I))
                same_property = alternative.section.split('.')[0] == chunk.section.split('.')[0]
                same_subject = alternative.metadata.get('entity', alternative.doc_id) == chunk.metadata.get('entity', chunk.doc_id)
                property_core = set(intent.topic) - {"period", "month", "year", "day", "people"}
                shared_property = property_core & self.runtime.retriever.topic_tokens[chunk.chunk_id] & self.runtime.retriever.topic_tokens[alternative.chunk_id]
                if same_property and same_subject and shared_property and quantities and competing and quantities != competing:
                    conflict = True
            if not conflict and choice.evidence_id in candidate_ids and self.verifier.verify(chunk.text, chunk.text).entailed:
                evidence = [dict(asdict(chunk), source_offsets={"start": int(chunk.metadata.get("start", 0)),
                    "end": int(chunk.metadata.get("end", len(chunk.text))), "basis": "normalized_source"},
                    corpus_hash=self.runtime.corpus_hash, phase="committed", final_turn_id=event.turn_id,
                    intent_revision=self.generation, source_hash=hashlib.sha256(chunk.text.encode()).hexdigest())]
        return {"claim_id": previous["claim_id"] if previous else f"c-{event.turn_id}-{intent.key[:8]}",
                "claim_revision": previous["claim_revision"] + 1 if previous else 1,
                "intent_key": intent.key, "query": intent.query,
                "dependencies": {"entities": list(intent.entity_ids), "topic": list(intent.topic), "constraints": list(intent.constraints)},
                "text": evidence[0]["text"] if evidence else f"The retrieved sources conflict on this request: {intent.query}." if conflict else f"I could not verify: {intent.query}.",
                "citations": [e["chunk_id"] for e in evidence], "evidence_event_ids": [retrieval_id] if evidence else [],
                "verification": "exact_extractive" if evidence else "uncertain", "evidence": evidence,
                "candidate_ids": sorted(candidate_ids), "verified_turn_id": event.turn_id,
                "withheld_reason": "conflicting_source_quantities" if conflict else None if evidence else "insufficient_relevant_evidence"}

    def _finish(self, result, event, started):
        elapsed = round((time.perf_counter()-started)*1000, 2)
        result["latency_ms"] = elapsed
        result["retrieval_events"].append(self.record("response_emitted", event, elapsed_ms=elapsed, backend=self.runtime.backend))
        if not self.closed:
            self.receipts[event.event_id] = result
        waiter = self.inflight.pop(event.event_id, None)
        if waiter is not None and not waiter.done():
            waiter.set_result(result)
        return result

    async def handle(self, event):
        try:
            return await self._handle(event)
        except BaseException as exc:
            owner = self.events.get(event.event_id, {}).get("owner")
            waiter = self.inflight.pop(event.event_id, None) if owner is asyncio.current_task() else None
            if waiter is not None and not waiter.done():
                waiter.set_exception(exc)
                waiter.exception()
            raise

    async def _handle(self, event):
        started = time.perf_counter()
        fingerprint = event.model_dump_json()
        raw_text = event.text
        fluent, disfluencies = normalize_disfluencies(raw_text)
        normalized, correction, ambiguous_correction = normalize_correction(fluent, self.runtime.decomposer.aliases)
        if correction or disfluencies:
            event = event.model_copy(update={"text": normalized})
        async with self.lock:
            if self.closed:
                raise ValueError("Session is closed")
            if event.event_id in self.events:
                if self.events[event.event_id]["fingerprint"] != fingerprint:
                    raise ValueError("event_id reused with different content")
                receipt = self.receipts.get(event.event_id)
                if receipt is not None:
                    return dict(receipt, duplicate=True, retrieval_events=[])
                previous_task = self.inflight.get(event.event_id)
            else:
                previous_task = None
        if previous_task is not None:
            result = await asyncio.shield(previous_task)
            return dict(result, duplicate=True, retrieval_events=[])
        async with self.lock:
            if len(self.events) >= 500:
                raise ValueError("Session event limit reached")
            if self.turns.get(event.turn_id, {}).get("final"):
                raise ValueError("Turn already finalized; use a new turn_id")
            if event.revision_of:
                prior = self.events.get(event.revision_of)
                if prior is None or prior["turn_id"] != event.turn_id:
                    raise ValueError("revision_of must reference this turn's earlier event")
            if event.sequence is not None:
                seqs = [e["sequence"] for e in self.events.values() if e["sequence"] is not None]
                if seqs and event.sequence <= max(seqs):
                    raise ValueError("sequence must increase")
            if event.target_intent_key and not event.is_final:
                raise ValueError("Refinement requires final transcript")
            is_format, is_social = presentation(event.text), social(event.text)
            updates, clarification = self._refinement(event.text, event.target_intent_key) if event.is_final and not (is_format or is_social) else (None, None)
            if ambiguous_correction:
                updates = None
                clarification = "I could not resolve that product correction. Please restate the question with the full product name."
            if translation_request(event.text):
                clarification = "Translation is not supported by this non-generative prototype. The original answer and citations are retained without searching."
            additions = self._late_detail_additions(event.text) if event.is_final and updates is None and not (is_format or is_social) else ()
            self.inflight[event.event_id] = asyncio.get_running_loop().create_future()
            self.events[event.event_id] = {"fingerprint": fingerprint, "turn_id": event.turn_id, "sequence": event.sequence, "owner": asyncio.current_task()}
            if self.turn_id != event.turn_id:
                self.cache.clear()
                self.previous, self.previous_text = (), ""
                self.turn_id = event.turn_id
            self.generation += 1
            revision = self.generation
            self.turns[event.turn_id] = {"final": event.is_final}
            trace = []
            if correction or disfluencies:
                trace.append(self.record("transcript_normalized", event, raw_text=raw_text,
                                         normalized_text=normalized, correction=correction,
                                         disfluencies=disfluencies))
            if event.revision_of or (self.previous_text and not event.text.lower().startswith(self.previous_text.lower())):
                trace.append(self.record("provisional_invalidated", event, revision_of=event.revision_of,
                                         discarded_candidates=sum(len(v) for v in self.cache.values())))
                self.cache.clear()
            parsed = tuple(updates.values()) if updates else additions or self.runtime.decomposer.split(event.text) if not (is_format or is_social) else ()
            if len(self.runtime.decomposer.entities(event.text)) > 1 and any(
                not i.entity_ids and re.search(r"\b(?:it|its|they|their|them)\b", i.query, re.I)
                for i in parsed
            ):
                clarification = "That follow-up could refer to more than one product. Name the product for each question."
            if is_format or is_social:
                decision, reason = "suppress", "presentation_only" if is_format else "social_turn"
            elif clarification:
                decision, reason = "wait", "ambiguous_refinement"
            elif event.is_final:
                decision, reason = "commit_retrieve", "targeted_delta" if updates or additions else "final_transcript"
            elif presentation_prefix(event.text):
                decision, reason = "wait", "possible_presentation_request"
            else:
                stable = tuple(i for i in parsed if i.topic and any((p.entity_ids == i.entity_ids or not p.entity_ids and i.entity_ids) and set(p.topic) <= set(i.topic) for p in self.previous))
                incomplete = bool(re.search(r"\b(?:and|or|not|without|between|instead of|rather than|for|in|with)\s*$", event.text, re.I))
                decision, reason = ("provisional_retrieve", "stable_searchable_intents") if stable and not incomplete and len(terms(event.text)) >= 3 else ("wait", "awaiting_stable_intent")
            trace.append(self.record("controller_decision", event, decision=decision, reason=reason, revision=revision))
            diagnostic = getattr(self.runtime.decomposer, "consume_diagnostic", lambda: None)()
            trace.append(self.record("intents_decomposed", event, intents=[i.public() for i in parsed],
                                     method=self.runtime.decomposer.method,
                                     decomposer_diagnostic=diagnostic))
            self.previous, self.previous_text = parsed, event.text
            if decision in {"wait", "suppress"}:
                result = self._snapshot(event, decision, reason, trace, parsed, answer=is_format and bool(self.claims), clarification=clarification)
                return self._finish(result, event, started)
            todo = tuple(i for i in parsed if event.is_final or self._cache_key(i) not in self.cache)
        try:
            results = await asyncio.wait_for(asyncio.gather(*(self._retrieve(event, i, event.is_final) for i in todo)), timeout=30)
        except asyncio.TimeoutError:
            results = []
            trace.append(self.record("retrieval_timeout", event, reason="30 second deadline; no unverified facts emitted"))
        async with self.lock:
            for item in results:
                trace.extend(item[-1])
            if self.closed or revision != self.generation:
                trace.append(self.record("stale_result_discarded", event, revision=revision, current_revision=self.generation))
                result = self._snapshot(event, "wait", "stale_result_discarded", trace)
            elif not event.is_final:
                for intent, ids, _, _, _ in results:
                    self.cache[self._cache_key(intent)] = ids
                result = self._snapshot(event, decision, reason, trace, parsed)
            else:
                found = {intent.key: (candidates, retrieval_id) for intent, _, candidates, retrieval_id, _ in results}
                old_claims = list(self.claims)
                updated, changed = [], []
                if updates:
                    for old in old_claims:
                        if old["intent_key"] not in updates:
                            updated.append(old)
                            continue
                        intent = updates[old["intent_key"]]
                        candidates, rid = found.get(intent.key, ((), "timeout"))
                        new = self._claim(intent, candidates, rid, event, old)
                        updated.append(new)
                        changed.append(new["claim_id"])
                elif additions:
                    updated.extend(old_claims)
                    for intent in parsed:
                        candidates, rid = found.get(intent.key, ((), "timeout"))
                        new = self._claim(intent, candidates, rid, event)
                        updated.append(new)
                        changed.append(new["claim_id"])
                else:
                    for intent in parsed:
                        candidates, rid = found.get(intent.key, ((), "timeout"))
                        new = self._claim(intent, candidates, rid, event)
                        updated.append(new)
                        changed.append(new["claim_id"])
                for intent in parsed:
                    self.intents[intent.key] = intent
                self.claims = updated
                self.version += 1
                old_ids, new_ids = {c["claim_id"] for c in old_claims}, {c["claim_id"] for c in updated}
                patch = {"version": self.version, "parent_version": self.version - 1 or None,
                         "added": sorted(new_ids-old_ids), "removed": sorted(old_ids-new_ids),
                         "replaced": sorted(set(changed)&old_ids), "preserved": sorted((new_ids&old_ids)-set(changed))}
                self.history.append(patch)
                self.cache.clear()
                for c in updated:
                    if c["claim_id"] in changed:
                        trace.append(self.record("claim_verified", event, claim_id=c["claim_id"], verification=c["verification"],
                                                 citations=c["citations"], candidate_ids=c["candidate_ids"], intent_id=c["intent_key"]))
                trace.append(self.record("answer_version", event, **patch))
                result = self._snapshot(event, decision, reason, trace, parsed, changed, answer=True)
            return self._finish(result, event, started)

    async def close(self):
        async with self.lock:
            self.closed = True
            self.generation += 1
            for waiter in self.inflight.values():
                if not waiter.done():
                    waiter.cancel()
            for value in (self.cache, self.claims, self.history, self.intents, self.telemetry, self.receipts, self.events, self.inflight):
                value.clear()
