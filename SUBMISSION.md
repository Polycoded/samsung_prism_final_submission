# CiteFrontier hackathon submission

CiteFrontier is a text-only, local Streaming Live RAG prototype. It retrieves from
stable partial input, validates evidence after final commit, decomposes compound
questions, rejects stale correction results, preserves unaffected claims during
refinement, and abstains when its corpus cannot support an answer. It uses no LLM,
microphone, or voice pipeline.

## Start in official mode

```powershell
docker compose -f prototype/docker-compose.yml up --build
```

Open `http://127.0.0.1:8000`. The submitted container profile uses BM25 + MiniLM
dense retrieval, cross-encoder reranking, exact extraction, local session state, and guarded DistilBERT
intent boundaries with spaCy as the explicit fallback. `CITEFRONTIER_DEMO=0`
keeps authored replay controls disabled unless it is explicitly set to `1`.

For the judged live presentation, run `prototype/demo/start-demo.ps1`. It loads
the packaged DistilBERT boundary checkpoint in guarded `auto` mode: accepted
high-confidence BERT spans are served and spaCy remains the explicit fallback.
The homepage reports the actual BERT-served count, minimum confidence, and
fallback count for the current session.

## Architecture

The browser sends timestamped transcript messages over WebSocket. A session-scoped
controller chooses WAIT, tentative retrieval, final commit, targeted refinement,
or presentation suppression. Parsed intents retrieve concurrently from the active
corpus. Only candidates checked against the final intent can support exact extracts.
Claims carry candidate IDs, source hashes, sections, and offsets. See
`prototype/docs/architecture-brief.md` and `prototype/docs/event-protocol.md`.

## Measured gates

| Gate | Local result | Status |
|---|---:|---|
| G1 reproducible container and replay | 60/60 WebSocket cases | Local pass |
| G2 eligible early retrieval | 37/40 (92.5%) | Local pass |
| G3 compound identification | 15/15 (100%) | Local pass |
| G4 exact extract support | 90/90 (100%); zero fabricated IDs | Local pass |
| G5 refinement continuity | 10/10 scenarios | Local pass |
| G6 trace coverage | 100% | Local pass |

These use the frozen, author-known venue-domain acceptance set against the same
dense/BERT profile launched by Docker. They are not an official Samsung score or
a blind benchmark.

## Authoritative data

- Runtime corpus: `prototype/corpus.json`
- Human-readable sources: `prototype/corpus/sources/`
- Gated benchmark: `evaluation/acceptance-v1.json`
- Development benchmark: `evaluation/development-v1.json`
- Dataset manifest: `evaluation/dataset-manifest.json`

SHA-256 values are recorded in `evaluation/dataset-manifest.json`. ATIS/SNIPS is
used only for the separate boundary-training experiment and is absent from the
runtime, gate evaluator, and submission archive.

## Organizer conference corpus

Open **Organizer corpus** and upload `.md`, `.txt`, or corpus `.json` files. The
upload replaces the corpus only for that WebSocket session, keeps citations and
source inspection, and is discarded on disconnect. **New session** restores the
bundled corpus. Bundled G2-G4 scores remain visibly separate from uploaded data.

## Reproduce from the repository

```powershell
.\.venv\Scripts\python -m unittest discover -s prototype/tests -v
.\.venv\Scripts\python -m unittest discover -s tests -v
.\.venv\Scripts\python -m evaluation.replay --backend dense --out prototype/reports/scorecard.json
```

Or verify the submitted container end to end with one command:

```powershell
docker compose -f prototype/docker-compose.yml --profile verify up --build --abort-on-container-exit --exit-code-from replay
```

The GitHub repository is the submission artifact. Generated archives, media,
training splits, secrets, caches, intermediate checkpoints, and local environments
are excluded by `.gitignore`. The promoted BERT checkpoint is tracked with Git LFS.

## Known limits and guide-format boundary

The supplied Theme 4 guide asks for a short video and a page-bounded architecture
brief. Per submission instruction, this package intentionally contains neither
video nor PDF. The architecture and live walkthrough are Markdown. Official
organizer-corpus validation and unseen relevance judging remain pending. The Docker
runtime was built and replayed successfully, and the final 145-file Git index passes
the repository audit. Independent organizer certification is still pending. Upload
conversion does not include PDF/OCR.
