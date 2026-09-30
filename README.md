# CiteFrontier

**Streaming retrieval that starts early, decomposes messy multi-intent questions, and commits only source-verifiable answers.**

CiteFrontier is a local, non-generative Streaming Live RAG prototype for Samsung PRISM Theme 4. It processes timestamped transcript updates, starts retrieval when an intent becomes stable, isolates multiple sub-questions, rejects stale work after corrections, preserves unaffected claims during refinement, and abstains when the active corpus cannot support an answer.

The submitted runtime uses a trained local DistilBERT intent-boundary tagger in guarded `auto` mode. High-confidence, structurally valid BERT spans are served; spaCy dependency rules are the explicit fallback. Answers are exact extracts from the active corpus, so the runtime uses no LLM, external answer source, or generated citation.

## Measured local results

| Gate | Result | Target |
|---|---:|---:|
| G1 · reproducible replay | 60/60 scenarios | Pass/fail |
| G2 · eligible early retrieval | 37/40 (92.5%) | ≥80% |
| G3 · compound identification | 15/15 (100%) | ≥70% |
| G4 · supported extracts | 90/90 (100%) | ≥85% |
| Fabricated citation IDs | 0 | 0 |
| G5 · refinement continuity | 10/10 scenarios | Verified |
| G6 · trace coverage | 985/985 (100%) | 100% |

These are author-known local acceptance results over the bundled fictional LumaHome venue-domain control corpus and `evaluation/acceptance-v1.json`. They are not official Samsung scores or an independent blind benchmark. ATIS/SNIPS data was used only to train the boundary detector and is not the live corpus or gated evaluation dataset.

## Run the submitted Docker profile

The promoted BERT checkpoint is stored with Git LFS. After cloning:

```powershell
git lfs pull
docker compose -f prototype/docker-compose.yml up --build
```

Open `http://127.0.0.1:8000`. If that port is occupied:

```powershell
$env:CITEFRONTIER_PORT=8014
docker compose -f prototype/docker-compose.yml up --build
```

The default container keeps authored replay fixtures disabled. For the judged walkthrough, use the local presentation launcher:

```powershell
.\prototype\demo\start-demo.ps1
```

Then open `http://127.0.0.1:8013` and play the messy transcript. The homepage shows the live BERT-served count, minimum accepted confidence, fallback count, detected sub-questions, exact citations, and session trace.

## What to demonstrate

1. Play the disfluent `umm / what what / uh / erm` transcript.
2. Point out early retrieval before the final transcript is committed.
3. Show the three BERT-separated intents and three independently cited extracts.
4. Open a citation and inspect the exact source text, section, offsets, and retrieval event.
5. Run the S1-to-S2 correction and show stale evidence being discarded.
6. Apply a late detail and show only the affected claim change.
7. Request bullet formatting and show that retrieval is suppressed.
8. Ask an unsupported question and show an uncited abstention.
9. Open **Validation** for G2-G4 evidence.
10. Open **Organizer corpus** to upload conference documents and a matching labeled benchmark.

The full presenter flow is in [`prototype/demo/demo_script.md`](prototype/demo/demo_script.md).

## Organizer corpus evaluation

The **Organizer corpus** panel accepts up to 25 `.md`, `.txt`, or corpus `.json` files for the current WebSocket session. Uploaded documents replace the bundled corpus only for that session and are discarded on disconnect. A matching labeled benchmark can then be run from the same panel; its score appears separately from the bundled G2-G4 results.

Training-style ATIS/SNIPS JSON is rejected by the uploader. New-session reset restores the bundled LumaHome corpus.

## Runtime architecture

```text
Timestamped transcript updates
  → WAIT / provisional retrieve / final commit / suppress
  → guarded DistilBERT boundary tagging
  → spaCy fallback and shared-scope enrichment
  → parallel per-intent retrieval
  → final-intent candidate revalidation
  → exact source extraction or explicit abstention
  → versioned claims, citations, and structured telemetry
```

Tentative candidates can reduce endpoint work, but they cannot support a final claim until revalidated against the committed transcript. Corrections increment the session generation so superseded asynchronous results cannot mutate the answer. Every factual claim must copy text from a real active-corpus chunk and cite an ID present in its committed candidate set.

See [`prototype/docs/architecture-brief.md`](prototype/docs/architecture-brief.md) and [`prototype/docs/event-protocol.md`](prototype/docs/event-protocol.md).

## Reproduce the checks

```powershell
.\.venv\Scripts\python -m unittest discover -s prototype/tests -v
.\.venv\Scripts\python -m unittest discover -s tests -v

$env:CITEFRONTIER_PARSER='auto'
$env:CITEFRONTIER_BERT_MODEL=(Resolve-Path 'bert_intent_tagger/model/checkpoints/best').Path
.\.venv\Scripts\python -m evaluation.replay --backend dense --out prototype/reports/scorecard.json
```

Current verification:

- 58/58 prototype tests
- 13/13 core tests
- 60/60 guarded-BERT acceptance scenarios
- 60/60 cases through the Docker WebSocket endpoint
- browser checks at 390, 768, and 1440 pixels
- organizer upload and labeled benchmark flow
- GSAP motion and reduced-motion behavior
- zero browser JavaScript errors in the tested flows

Detailed evidence is in [`SUBMISSION-MANIFEST.md`](SUBMISSION-MANIFEST.md), [`SUBMISSION.md`](SUBMISSION.md), and [`prototype/reports/benchmark-report.md`](prototype/reports/benchmark-report.md).

## Repository map

- `prototype/` — submitted web application and WebSocket runtime
- `prototype/corpus.json` — running fictional venue-domain corpus
- `prototype/corpus/sources/` — human-readable source documents
- `bert_intent_tagger/model/checkpoints/best/` — promoted boundary checkpoint
- `evaluation/acceptance-v1.json` — frozen gated acceptance set
- `evaluation/development-v1.json` — development cases
- `evaluation/dataset-manifest.json` — dataset schema and hashes
- `schemas/` — telemetry and event contracts
- `prototype/reports/` — benchmark and browser verification evidence
- `evaluation/results/` — compact retrieval ablation summaries

## Boundaries

The bundled corpus and acceptance suite are disclosed synthetic controls. Official organizer-corpus validation remains pending. The submitted container runs BM25/MiniLM hybrid retrieval, cross-encoder reranking, and guarded DistilBERT boundaries with spaCy fallback. The live product performs text processing only and contains no microphone or voice pipeline.

## Demo Video

[Watch the CiteFrontier Demo Video](https://drive.google.com/file/d/14lOkclRvr-2hIA05pVYTHJVVCGAQOb2u/view?usp=sharing)
