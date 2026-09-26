# Submission verification manifest

Generated 26 September 2026 for the text-only CiteFrontier submission.

## Input hashes (SHA-256)

| File | SHA-256 |
|---|---|
| `prototype/corpus.json` | `693aeffa6ddd7483ee31fd0ed220eeef96ef720f2e6b6b5ffc6b0de69de789bb` |
| `evaluation/acceptance-v1.json` | `beae23a801229bf493b472083437b589724e07312640c18397411ad1e2644641` |
| `evaluation/development-v1.json` | `4ab1caf17f35b3b1e865a8c67957b62e14129036f6f1f17908672285090635bf` |

## Verification

| Check | Result |
|---|---|
| Prototype tests | PASS, 58/58 |
| Core tests | PASS, 13/13 |
| Frozen dense/BERT acceptance replay | PASS, 60/60 |
| G2 | 37/40 (92.5%) |
| G3 | 15/15 (100%) |
| G4 | 90/90 supported extracts; zero fabricated IDs |
| G6 trace coverage | 985/985 (100%) |
| Official-mode WebSocket replay | PASS, 60/60 |
| Browser upload and responsive layout | PASS at 390, 768, and 1440 px; no JavaScript errors or overflow |
| GSAP enhancement layer | PASS: local 3.13.0 asset, replay/claims/citation/inspector/dialog, reduced motion, no JavaScript errors |
| Organizer benchmark lab | PASS: messy sample 6/10, four visible failures, zero fabricated IDs |
| Disfluent transcript handling | PASS: raw/cleaned telemetry, fixed fillers and repetitions, no LLM |
| Guarded BERT auto replay | PASS: 60/60; BERT served 152/152 decompositions, 147 agreements, 5 high-confidence disagreements, 0 fallbacks |
| Submitted Docker profile | PASS: BM25/MiniLM retrieval, cross-encoder reranking, `auto:bert_intent_boundary+spacy_dependency_rules` |
| Submitted Docker WebSocket replay | PASS, 60/60 through the running container |
| Final repository audit | PASS: 145 tracked files; no PDF, video, ZIP, screenshots, ATIS/SNIPS splits, caches, secrets, or Neo4j dependency |
| Fresh repository-copy Docker replay | PASS, 60/60 through the running dense/BERT container |

The acceptance data and bundled LumaHome corpus are author-known synthetic venue
controls. Results are local and do not claim official or blind validation. The
GitHub repository is the submission artifact; generated archives are not required.
