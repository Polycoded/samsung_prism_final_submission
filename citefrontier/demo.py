"""Run a short terminal walkthrough of the validation prototype."""

from __future__ import annotations

from .engine import CiteFrontierEngine
from .fixtures import fixture_retriever, multi_intent_trace


def main() -> None:
    engine = CiteFrontierEngine(fixture_retriever())
    session = engine.new_session()
    print(f"Session: {session.session_id}")
    for event in multi_intent_trace():
        output = engine.process_stream(session, event)
        print(f"{event.timestamp_s:>3.1f}s | {output.action.decision.value:>21} | {output.action.reason}")
        for retrieval_id in output.retrieval_event_ids:
            print(f"      retrieval: {retrieval_id}")
    print("\nGrounded answer:\n" + (session.latest.render() if session.latest else "No answer"))
    print("\nTelemetry events:")
    for event in engine.telemetry.events:
        print(f"- {event.timestamp_s:>3.1f}s {event.event_type}: {event.payload}")


if __name__ == "__main__":
    main()
