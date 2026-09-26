# CiteFrontier — Project Report

**Project:** CiteFrontier, Streaming Live RAG for Samsung PRISM Theme 4
**Report date:** 26 September 2026
**Status:** locally verified on the disclosed synthetic control corpus; organizer and blind official validation remain pending.

## Summary

CiteFrontier is a text-only retrieval system for changing, live transcripts. It begins candidate retrieval when a partial question becomes stable, but tentative results can never become factual answers. When final input arrives, it splits compound questions, retrieves evidence for each intent, verifies the evidence against final wording, and returns exact source extracts with citations. It abstains when evidence is missing or conflicting.

The answer layer is non-generative: no LLM, web search, microphone, speech-recognition service, or external answer source is used at inference time. Claims are copied from the active corpus, enabling source inspection and explicit zero generator-token cost.

## Architecture

```text
Transcript hypothesis
  -> wait / provisional retrieval / final commit / refine / suppress
  -> guarded DistilBERT decomposition with spaCy fallback
  -> BM25 + MiniLM retrieval, rank fusion, cross-encoder reranking
  -> final-intent evidence verification
  -> versioned cited claims or uncited uncertainty
  -> WebSocket update and structured telemetry
```

The submitted browser/WebSocket application is in `prototype/`. It renders live controller decisions, sub-questions, cited claims, source inspection, claim versions, telemetry, and organizer-corpus evaluation. Formatting-only turns reuse existing verified claims without a new search. Corrections invalidate older candidate state, and late details update only the affected claim.

## Retrieval and grounding

The submitted dense runtime uses BM25, `all-MiniLM-L6-v2`, reciprocal-rank fusion, and `ms-marco-MiniLM-L-6-v2` reranking. Models are provisioned during Docker build and loaded offline.

Compound questions become scoped intents with original spans, entities, topics, and constraints. The local guarded DistilBERT boundary tagger serves valid high-confidence spans; spaCy/rules are the fallback. Every emitted factual claim must be an exact extract from an active-corpus chunk, cite a real final-candidate ID, and pass extractive verification. Unsupported concepts, unsafe source instructions, and conflicting quantities produce uncertainty without a citation.

## Session isolation and telemetry

State is per WebSocket connection and is cleared at disconnect. Uploaded organizer corpora are in memory, session-specific, and discarded at disconnect. Telemetry records IDs, timestamps, controller decisions, decomposition, retrieval events, candidate IDs, citations, answer-version lineage, latency, and zero generation cost.

The organizer panel accepts Markdown, text, and valid corpus JSON; it keeps uploaded-corpus benchmarks separate from bundled LumaHome results.

## Recorded local verification

The frozen acceptance set contains 60 author-known synthetic scenarios covering single and compound questions, corrections, selective refinements, presentation/mixed turns, and unsupported requests.

| Gate | Local result |
|---|---:|
| Reproducible replay | 60/60 scenarios |
| Eligible early retrieval | 37/40 (92.5%) |
| Compound identification | 15/15 (100%) |
| Exact supported extracts | 90/90 (100%) |
| Fabricated citation IDs | 0 |
| Refinement continuity | 10/10 scenarios |
| Trace coverage | 985/985 (100%) |

Recorded checks also cover 58/58 prototype tests, 13/13 core tests, 60/60 Docker WebSocket replay cases, browser flows without JavaScript errors, responsive layouts at 390/768/1440 pixels, organizer upload and benchmark behavior, reduced-motion behavior, stale-result rejection, conflict abstention, and formatting suppression.

The recorded dense/BERT run measured 138.48 ms p50 and 241.25 ms p95 warm endpoint latency, with 36.94 seconds cold initialization. Candidate reuse reduced searches from 146 to 104 (28.8%) compared with streaming without reuse; final-only mode had no early retrieval. This documents a work-versus-earliness trade-off, not a general speed claim.

## Reproducibility

```powershell
git lfs pull
docker compose -f prototype/docker-compose.yml up --build
```

Open `http://127.0.0.1:8000`. The walkthrough launcher is `prototype/demo/start-demo.ps1`. Test, replay, and Docker verification commands are in `README.md` and `SUBMISSION.md`.

## Submission boundaries

Only the promoted BERT checkpoint required by Docker is tracked. Intermediate checkpoints, raw datasets, converted splits, environments, caches, recordings, and local evaluation outputs are ignored. The training-curves record uses no absolute local path. Raw external-training utterances and a duplicate technical report were removed from final submission content.

The bundled LumaHome corpus and acceptance suite are synthetic author-known controls, not an official Samsung score, blind benchmark, or organizer-corpus validation. PDF/OCR conversion, microphone capture, speech-to-text, translation, web search, and generative paraphrasing are intentionally out of scope.

## Conclusion

CiteFrontier shows how live retrieval can start early while final factual claims remain source-verifiable. Its correction handling, targeted refinements, compound-question decomposition, citations, abstention, session isolation, and telemetry are designed to be inspectable and testable. Organizer-corpus and hidden official replay validation remain the next required step.
