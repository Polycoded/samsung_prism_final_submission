# CiteFrontier Live - Benchmark and Edge-Case Report

Date: 26 September 2026
Verdict: passes disclosed local acceptance; official Samsung validation pending

## Evaluation contract

The frozen acceptance set contains 60 author-known synthetic scenarios: 10 single questions, 15 compound questions, 10 same-turn corrections, 10 selective refinements, five presentation/mixed turns, and 10 unsupported requests. Labels are inspected only after runtime output. This is a regression and mechanism test, not a blind estimate of organizer-corpus performance.

## Gate results

| Gate | Guide target | Recorded local result | Local verdict |
|---|---:|---:|---|
| G1 Reproducibility | One-command clean run | Docker build, health, dashboard, and WebSocket verified | Pass |
| G2 Early retrieval | >=80% eligible | 37/40, 92.5% | Pass locally |
| G3 Multi-intent identification | >=70% compound | 15/15 compound scenarios | Pass locally |
| G4 Factual grounding | >=85%; zero fabricated IDs | 90/90 exact-extractive claims; zero fabricated IDs | Pass locally |
| G5 Session refinement | Verified continuity | 10/10 refinement scenarios; preserved claim checks | Pass locally |
| G6 Trace coverage | 100% | Every emitted event has IDs, times, payload, and explicit token cost | Pass locally |

Warm endpoint latency in the submitted dense/BERT run was 138.48 ms p50 and 241.25 ms p95. Cold model/index initialization was 36.94 seconds. The non-generative answer layer records zero generator tokens and USD 0.00 inference token cost.

## Architectural ablations

### A1: candidate reuse versus no reuse

The submitted reuse configuration issued 104 searches with 42 cache reuses. The controlled lightweight ablation issued 146 searches with reuse disabled, so reuse removed 42 searches (28.8%) in that ablation. Latency was not controlled tightly enough to claim an improvement; the supported conclusion is reduced retrieval work.

### A2: streaming versus final-only

The final-only configuration passed the answer checks but triggered zero early searches by construction. Streaming triggered 37 of 40 eligible prefixes and retained the same final citation checks. This isolates the mechanism responsible for G2 rather than attributing final-answer quality to speculative retrieval.

### A3: lightweight versus dense retrieval

Earlier frozen LumaHome evaluation showed the lightweight hybrid at 16/24 exact citations and the dense reranked backend at 20/24 before shared-scope fixes. The final dense acceptance suite covers 90/90 expected evidence instances. These runs use different checkpoints of the implementation, so they document engineering progression rather than a clean current head-to-head speed comparison.

## Analyzed edge-case failure modes

### E1: stale evidence after an ASR correction

Failure mode: a slow S1 lookup finishes after the transcript changes to S2 and contaminates the answer. Mitigation: every event increments a generation; an older retrieval checks the current generation before commit and emits `stale_result_discarded`. The adversarial delayed-result test confirms only S2 evidence remains.

### E2: fabricated certainty for an unsupported topic

Failure mode: semantic similarity returns a nearby product passage for a concept absent from the corpus. Mitigation: vocabulary, entity, final-candidate, and evidence-overlap guards withhold the claim. Telepathy, cryptocurrency, unknown sibling products, and other unsupported cases emit uncertainty with no citation.

### E3: contradictory numeric evidence

Failure mode: two passages state different warranty durations and the highest-ranked passage is presented as settled fact. Mitigation: candidate evidence for the same entity/property is checked for competing quantities. A conflict produces `conflicting_source_quantities` and no citation.

### E4: presentation-only retrieval

Failure mode: “repeat your last answer in two bullets” launches a new vector search and introduces drift. Mitigation: the full-match presentation grammar suppresses retrieval, preserves claims and citations, and leaves the search count and answer version unchanged. Mixed factual requests are excluded from suppression.

### E5: over-fragmented coordinated phrases

Failure mode: splitting every “and” breaks numeric ranges or coordinated names. Mitigation: protected ranges and conservative grammar avoid splitting known single-intent coordination. The guarded BERT parser serves high-confidence boundaries and falls back to spaCy when confidence or structure checks fail. Boundary errors from the broader 200-case development review remain regression candidates; the frozen 60-case submission replay passes with the guarded parser.

## Remaining boundary

The organizer corpus and hidden replay traces have not been supplied. Corpus-specific indexing, the official replay schema, and official G1-G6 measurements must be rerun before submission claims are upgraded from local acceptance to official compliance.


## 20 September controlled retrieval ablations

All three runs use the same frozen acceptance set, corpus, parser and current
code, changing candidate reuse or early retrieval. They are sequential local
runs, not randomized paired latency experiments. No speed improvement is claimed.

| Configuration | Passed | Searches | Early streams | Endpoint p50 / p95 ms |
|---|---:|---:|---:|---:|
| audit-current | 60/60 | 104 | 37 | 9.25 / 12.80 |
| audit-no-reuse | 60/60 | 146 | 37 | 9.74 / 13.65 |
| audit-final-only | 60/60 | 94 | 0 | 10.08 / 13.40 |

Candidate reuse reduces searches from 146 to 104 (28.8%) relative to the streaming
no-reuse ablation. Final-only uses 94 searches but cannot retrieve before the
endpoint. Thus streaming has a work/earliness trade-off; it does not universally
reduce total searches relative to final-only. Raw records are under evaluation/results/audit-*.

Additional discovered failure: word-by-word presentation prefixes triggered a
search even though the final request was suppressed. A possible-presentation
prefix guard now waits, retaining mixed factual requests as searchable. Four
authored formatting/translation probes issued zero unnecessary searches after
the fix; this tiny probe set is not a held-out false-trigger estimate. Translation
is explicitly unsupported and preserves the original answer.

Current G2-G4: 37/40 early (92.5%), 15/15 compound scenarios (100%), 90/90 exact
extracts supported with zero fabricated IDs. ATIS/SNIPS is excluded from these
measurements. G4 checks attribution and does not imply general answer correctness.

Organizer corpus uploads are unscored until paired with their own labeled replay
set. They never inherit these bundled scores.
