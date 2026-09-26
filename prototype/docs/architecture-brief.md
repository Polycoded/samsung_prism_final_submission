# CiteFrontier Live - System Architecture Brief

Status: final submission reviewed 26 September 2026; official validation pending
Scope: Samsung PRISM Theme 4, Streaming Live RAG

## 1. Design objective

CiteFrontier processes timestamped transcript hypotheses while a user is still speaking. It retrieves early when an intent becomes stable, but tentative candidates cannot support an answer until the final transcript revalidates them. A final utterance may become several independently searchable intents. Later constraints update the active answer in place, and formatting-only turns reuse the verified answer without searching again.

The implementation favors a small, inspectable pipeline: one controller, one decomposer, one hybrid retriever, one evidence verifier, and ephemeral session state. The default answer layer is exact extraction from the supplied corpus, so it uses no generator tokens and cannot introduce uncited factual prose.

## 2. Event path

```text
Timestamped transcript event
  -> controller: WAIT / provisional retrieval / final commit / suppress
  -> decomposer: scoped intent records with source offsets
  -> parallel retrieval: BM25 + MiniLM dense search
  -> reciprocal-rank fusion and cross-encoder reranking
  -> final candidate revalidation and exact-entailment check
  -> claim-level answer version with citations or explicit uncertainty
  -> structured telemetry and WebSocket update
```

Non-final transcript events may populate a candidate cache. They never create answer claims. A correction increments the session generation, invalidates incompatible candidates, and prevents an older asynchronous result from committing. Final events rerank candidates against the final intent before promotion to evidence.

## 3. Controller and decomposition

The controller uses transcript stability, entity continuity, topic growth, terminal completeness, event revisions, and turn boundaries. It waits on incomplete fragments, starts provisional work on stable searchable prefixes, commits only final transcripts, and suppresses social or presentation-only turns. Mixed formatting and factual requests remain searchable.

The submitted decomposer runs a local DistilBERT boundary tagger in guarded `auto` mode. High-confidence, structurally valid BERT spans are served; a pretrained spaCy dependency parse plus conservative structural rules is the explicit fallback. The pipeline propagates shared entity scope, extracts constraints, keeps original character spans, and removes only exact canonical duplicates. Compound intents run concurrently. The tagger reached 99.80% exact recovered-boundary accuracy on 2,959 MixATIS/MixSNIPS utterances. On an expanded 200-case curated synthetic venue review set with ASR-style inputs and coordination hard negatives, accepted BERT output reached 91.0% exact spans and guarded auto reached 88.5%, versus 57.5% for rules. The venue review set remains pending independent human review, so these are local development measurements rather than official scores.

## 4. Retrieval, ranking, and grounding

The semantic profile combines BM25 and `all-MiniLM-L6-v2` dense rankings with reciprocal-rank fusion and reranks with `ms-marco-MiniLM-L-6-v2`. Model revisions are pinned and loaded from the local cache. The deterministic lightweight profile uses lexical scoring for container and offline demonstrations.

Every answer claim is copied exactly from one committed corpus chunk. A citation must be a real chunk ID, must occur in the final intent's candidate set, and must pass exact-extractive verification. Unknown concepts, conflicting quantities, unsafe instruction-like passages, and missing evidence produce an uncertainty statement without a citation. Corpus source files, normalized offsets, hashes, and a corpus manifest provide provenance.

## 5. Refinement and session state

Session state holds active intents, claims, candidate cache entries, version history, event receipts, and telemetry. A targeted late detail retrieves only the affected delta. Unaffected claims retain their ID, evidence, and citation; changed claims increment their revision. Conservative declarative follow-ups can add scoped constraints without clearing prior facts. Ambiguous refinements ask for clarification.

All state is in memory and scoped to one WebSocket connection. The server clears claims, caches, receipts, and telemetry on disconnect. Telemetry access requires that session's bearer token. Nothing is written to a cross-session profile.

## 6. Observability and cost

Every event records client time, server elapsed time, session/event/turn IDs, controller decisions, decomposition results, retrieval triggers, candidate IDs, committed citations, answer-version lineage, and cost. The current pipeline is non-generative, so every event explicitly records zero input tokens, zero output tokens, and USD 0.00 with the basis `non_generative_pipeline`. Raw traces are exportable as JSONL and described by `schemas/telemetry-event.schema.json`.

## 7. Corpus isolation and deployment

At inference time the runtime reads only the configured local corpus, bundled promoted boundary checkpoint, and pinned retrieval models provisioned during the image build. It has no web-search or external-knowledge path. Evaluation labels live outside the corpus and are supplied to the evaluator only after the runtime responds. The Docker profile uses guarded BERT decomposition, BM25/MiniLM retrieval, and cross-encoder reranking. Runtime model loading is offline.

## 8. Failure behavior and trade-offs

- Early retrieval reduces endpoint work but may waste a search when speech changes; generation barriers prevent factual leakage.
- Rules are fast and auditable but miss some implicit boundaries; the isolated BERT tagger is the measured upgrade path.
- Exact extraction maximizes attribution and reproducibility but produces less fluent answers than generation.
- Candidate reuse reduced searches by 42 in the recorded run, while latency varied enough that no latency improvement is claimed.
- The supplied organizer corpus and hidden replay suite remain unavailable. All displayed scores are clearly marked author-known synthetic controls.

The current text-only UI exposes sub-questions, correction resolution, citation inspection, and claim diffs. Demo queries are separate presentation fixtures and can be disabled with CITEFRONTIER_DEMO=0. No microphone or LLM is required.

Organizer uploads are in-memory, per-connection corpora, with independent source hashes. Markdown, text, and chunk JSON are accepted; dataset/training JSON is rejected. Uploading does not change bundled benchmark scores or other sessions. Presentation prefixes wait without retrieval; translation is explicitly unsupported without invoking a generator.

## 9. Reproducibility

```powershell
docker compose -f prototype\docker-compose.yml up --build
```

The repository includes pinned dependencies, corpus and model manifests, unit/API/adversarial tests, a 60-case replay set, raw traces, ablation outputs, browser QA, and a live walkthrough script. The final presentation video is produced separately by the team.
