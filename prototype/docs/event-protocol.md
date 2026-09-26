# Local event protocol

The PDF provides illustrative records, not a complete wire contract. Confirm any
organizer replay adapter before official evaluation. This document specifies the
actual running prototype, not an asserted Samsung schema.

- Client connects to `/ws/stream`; server emits `ready` with session ID, bearer
  token, backend, parser, and corpus hash.
- Client sends timestamped hypotheses matching `schemas/transcript-input.schema.json`.
  Text is the cumulative hypothesis, not just the newly appended words.
- Server emits one `update` per event matching `schemas/live-output.schema.json`.
  `sub_queries` contains structured intent records; `uncertainty` is an array.
  These differ from the illustrative PDF's string lists/string field.
- Each update carries `retrieval_events` matching `schemas/telemetry-event.schema.json`,
  latency, committed citations, answer versions, and explicit zero generator cost.
- A correction preserves raw and normalized text in `transcript_normalized`.
- A formatting update retains claims/citations and supplies `presentation_items`
  for numbered bullet grouping. It does not generate a paraphrase or translation.
- Organizer upload: `{"type":"corpus_upload","files":[{"name":"Venue.md","text":"..."}]}`.
  Success emits `corpus_loaded` with a new session ID/token/hash and document/chunk
  counts. The previous session is closed. Failed validation leaves it unchanged.
- `GET /session/{id}/corpus` and `/session/{id}/telemetry` require the session's
  bearer token. Disconnect clears session state and its uploaded corpus reference.
- API errors return `type: error` with a detail, and an event ID when available.

This is event-level answer streaming. It does not emit generated tokens.
