# CiteFrontier Live

CiteFrontier Live is a local, corpus-grounded Streaming Live RAG prototype for Samsung PRISM Theme 04. It starts retrieval from stable transcript prefixes, keeps tentative evidence out of answers, decomposes compound questions, rejects stale results after ASR corrections, and updates only affected claims after a late detail.

The bundled LumaHome corpus is fictional and exists only as a disclosed control. The included results are author-known local acceptance results, not an official Samsung score or an independent blind benchmark.

## Text interaction upgrades

The frontend vendors GSAP 3.13.0 locally for short, purposeful state transitions:
pipeline progress, intent decomposition, claim updates, evidence inspection, and
occasional dialogs. It makes no network request and honors `prefers-reduced-motion`;
all behavior remains available if the motion layer cannot initialize. License and
package provenance are recorded in `prototype/static/vendor/GSAP-NOTICE.txt`.

The default view focuses on the question and answer; **Show inspector** reveals
scenarios, retrieval events, and version history. Clicking a citation opens its
source. **Ctrl+Enter** submits the draft, and **Copy answer with citations** keeps
references attached. Updated claims can reveal their previous wording; unaffected
claims are labelled unchanged. Presentation-only formatting retains evidence.

Explicit trailing corrections such as `LumaPad S1 warranty, I meant S2` resolve
against corpus entity aliases with deterministic rules. The raw input and resolved
query are recorded in session telemetry and the UI shows “Understood as”. Unknown
or ambiguous replacements ask for clarification. This is a narrow entity correction
rule, not general text rewriting or semantic understanding. It needs no LLM.

Speech-like text can contain a narrow, inspectable set of disfluencies. The
runtime removes only `um`/`umm`, `uh`, `erm`/`er`, `ah`, and immediately repeated
words before parsing. The raw transcript, cleaned interpretation, and exact
removals remain in the `transcript_normalized` telemetry event and the UI displays
“Understood as.” This is deterministic cleanup rather than generative rewriting.

No microphone, recording, speech-recognition service, or generative model was added.
The existing dense profile uses local embedding/reranking models; the lightweight
profile uses lexical retrieval. The submitted parser is guarded DistilBERT with spaCy fallback.

Browser regression check (run the app on port 8011 first):

```powershell
.\.venv\Scripts\python -m prototype.tests.browser_text_flow
```

## Organizer corpus and G2-G4

Open **Validation** for G2-G4 measured on `prototype/corpus.json` with
`evaluation/acceptance-v1.json`. These named files currently contain fictional
LumaHome support data. `evaluation/development-v1.json` is development material;
ATIS/SNIPS belongs only to the separate BERT boundary experiment.

Current submitted-profile results: G2 37/40 (92.5%), G3 15/15 (100%), G4 90/90 exact
extracts supported (100%) with zero fabricated IDs. These are local synthetic
results, not hidden evaluation scores or proof of unseen-corpus correctness.

**Organizer corpus** accepts .md, .txt, and corpus .json. Uploads are held in
memory, replace only that WebSocket session's corpus, and disappear on disconnect.
New session restores the configured default corpus. JSON must have the same
chunk shape as `prototype/corpus.json`, with doc_id, section, text and optional
string metadata. Source labels and offsets remain inspectable. Markdown `##`
headings become citation sections. PDF/OCR conversion must happen before upload.
Limits: 25 files, 1 MB wire payload, 250 sections, 16,000 characters per section.
The benchmark panel never presents bundled scores as scores for uploaded material.

The homepage now includes an **Organizer evaluation lab**. After uploading a
corpus, an organizer can upload a labeled JSON array conforming to
`schemas/organizer-benchmark.schema.json` and run up to 50 questions against that
session corpus. Results show pass/fail per question, supported emitted extracts,
and fabricated citation IDs. They remain visibly separate from bundled G2–G4.
`prototype/demo/messy-conference/` provides a fictional stress kit with fillers,
immediate repetitions, missing punctuation, draft
contradictions, amended times, similar network names, compound questions, noisy
punctuation, and an unsupported request. Its deliberately honest result is 6/10;
all emitted extracts are source-supported and no citation ID is fabricated.

For Docker settings, copy `prototype/.env.example` to `prototype/.env`.
Official mode defaults to `CITEFRONTIER_DEMO=0`, which disables authored
presentation replay fixtures. Set it to `1` only for a rehearsed live presentation.
Fixtures live in `prototype/demo/scenarios.json`; retrieval never reads them.

## Quick start

Python 3.12 is recommended.

```powershell
uv venv .venv --python 3.12
uv pip install --python .venv\Scripts\python.exe -r prototype\requirements-lock.txt
.\.venv\Scripts\python -m prototype --backend lightweight
```

Open `http://127.0.0.1:8000`. The lightweight profile is deterministic and does not download models.

For the local semantic profile:

```powershell
uv pip install --python .venv\Scripts\python.exe -r prototype\requirements-dense.txt
.\.venv\Scripts\python -m prototype.prepare_models
.\.venv\Scripts\python -m prototype --backend dense
```

Model provisioning is explicit. Runtime loading uses pinned revisions from the local cache only and fails visibly when assets are missing.

### Guarded DistilBERT boundary detector

The trained checkpoint is packaged locally and is never downloaded at runtime:

```powershell
uv pip install --python .venv\Scripts\python.exe -r prototype\requirements-bert.txt
.\.venv\Scripts\python -m prototype --backend lightweight --parser shadow
```

Parser modes are `rules`, `spacy`, `bert`, `shadow`, and `auto`. `shadow` serves the existing splitter and writes both span sets plus agreement, latency, and fallback reason into the `intents_decomposed` telemetry event. `auto` serves structurally valid BERT spans at or above `CITEFRONTIER_BERT_THRESHOLD` (default `0.90`) and otherwise falls back to `CITEFRONTIER_FALLBACK_PARSER` (default `spacy`). Override the local checkpoint with `CITEFRONTIER_BERT_MODEL`.

The presentation launcher `prototype/demo/start-demo.ps1` now uses guarded
`auto` mode and the trained local checkpoint. On the frozen 60-case replay it
preserved 60/60 cases, G2 37/40, G3 15/15, G4 90/90, and zero fabricated IDs.
BERT served 152/152 decomposition events; 147 agreed with spaCy and five
high-confidence disagreements were accepted, with zero fallbacks. Mean BERT
boundary latency was 34.79 ms and the observed maximum was 148.99 ms. The
homepage reports live session BERT usage, minimum accepted confidence, and
fallback count. The submitted Docker profile uses the same guarded BERT mode
with spaCy as its explicit fallback.

The expanded 200-case curated synthetic venue review set includes punctuation-free ASR utterances and single-intent coordination hard negatives. Raw accepted BERT output measured 91.0% exact spans with 18 conservative fallbacks and 100% precision among accepted predictions; guarded `auto` measured 88.5% versus 57.5% for rules. The set is explicitly pending independent human review, so these remain local development measurements. The submitted runtime uses `auto`, retaining spaCy fallback for rejected predictions.

## What the demo proves

- `WAIT`, tentative retrieval, final commit, and presentation-only suppression are visible in telemetry.
- A correction increments the revision and late results from the superseded hypothesis are discarded.
- Compound intents retrieve concurrently and retain their shared subject.
- Tentative candidate IDs can be reused, but they are reranked and checked against the final intent before becoming committed evidence.
- Exact extractive claims cite only their final intent's candidate set.
- Unsupported topics, conflicting quantities, unknown sibling products, and instruction-like corpus text are withheld.
- Natural-language late details preserve unaffected claims and stable claim IDs.
- Session telemetry requires a per-session bearer token and all session state is cleared on disconnect.

The default answer layer uses verified exact extraction. It intentionally avoids a generative model so the safety behavior remains inspectable and reproducible.

## Rebuild the corpus

Only Markdown sources under `prototype/corpus/sources/` enter the runtime index. Evaluation labels live separately under `evaluation/`.

```powershell
.\.venv\Scripts\python -m prototype.ingest
```

This creates `prototype/corpus.json` and `prototype/corpus-manifest.json` with source hashes and character offsets.

## Tests and evaluation

### How multi-intent detection works

The submitted parser is a **local DistilBERT boundary tagger in guarded auto
mode**, not an LLM. Accepted high-confidence spans are served; spaCy dependency
analysis plus deterministic rules handles rejected predictions. The combined
decomposer recognizes corpus entity aliases, finds question/clause boundaries,
and carries a shared product into each request.
Adjacent questions separated by punctuation and `and also` are supported.
Implicit property lists split only when their properties are distinct corpus
section terms; a conjunction alone is insufficient. Thus `warranty period and
repair requirements` can split while `receipt and serial number` stays together.

For example, `For LumaPad S1, what is the warranty period? What receipt opens a
repair?` produces two scoped queries, both about LumaPad S1. Each query has source
offsets, an entity, topic tokens, constraints, and a stable canonical identifier.
Equivalent requests are deduplicated. Retrieval tasks run concurrently with
bounded work slots (local model inference can still serialize through a lock),
and each answer extract must cite that intent's final candidates.

An unambiguous `it` can inherit the last explicitly named product within the same
request. Ambiguous references after multiple products ask for clarification.
This is conservative scope propagation, not general coreference resolution.
Unknown paraphrases and complicated comparisons remain limitations. Detected
sub-questions now appear below the input in both the focused and inspector views.

The 26 September 2026 final submission review runs the complete prototype suite, including
boundary/scope regressions exercised with both rules and spaCy; the frozen
60-scenario lightweight replay passed 60/60 with 90/90 expected evidence instances.
Browser checks cover visible splitting and ambiguous-product clarification.
These are local development/regression results, not independent held-out accuracy.
Current results: `reports/text-improvements-acceptance.json` and
`reports/text-flow-qa.json`.

```powershell
.\.venv\Scripts\python -m unittest prototype.tests.test_live -v
.\.venv\Scripts\python -m unittest discover -s tests -v
.\.venv\Scripts\python -m evaluation.replay --backend dense --out prototype\reports\scorecard.json
.\.venv\Scripts\python -m prototype.tests.browser_check
```

The 60-scenario suite covers single and compound questions, correction, selective refinement, presentation-only turns, mixed presentation/factual turns, and unsupported requests. The 120-entry development set contains correlated variants from 10 query families and must not be presented as 120 independent questions.

Raw per-case results and telemetry are retained in JSON/JSONL. The in-product Validation dialog states the dataset and official-validation limitations.

## Container

```powershell
docker compose -f prototype\docker-compose.yml up --build
```

The container launches guarded BERT decomposition with BM25 + MiniLM dense retrieval and cross-encoder reranking at `http://127.0.0.1:8000`. Its pinned model assets are provisioned at image build time and inference is offline. If that host port is occupied, set `CITEFRONTIER_PORT`, for example `$env:CITEFRONTIER_PORT=8010`, before running Compose. Docker Desktop must be running.

One-command container verification starts the service, waits for health, and replays all 60 frozen WebSocket cases:

```powershell
docker compose -f prototype\docker-compose.yml --profile verify up --build --abort-on-container-exit --exit-code-from replay
```

## Important artifacts

- `prototype/docs/architecture-brief.md` — submitted architecture and scope
- `prototype/reports/scorecard.json` — semantic-profile local acceptance results
- `prototype/reports/browser-qa.json` — browser verification record
- `evaluation/results/` — ablations
- `prototype/demo/demo_script.md` — text-only live walkthrough

## Current boundary

Samsung corpus and official replay validation are pending. Generative paraphrasing and microphone ASR are outside this prototype. Guarded BERT is part of the submitted runtime, with spaCy as fallback.
