"""Session-scoped organizer benchmark runner for an uploaded corpus."""
from __future__ import annotations
import time
from uuid import uuid4
from .server_types import make_transcript_message


def validate_cases(raw):
    if not isinstance(raw, list) or not 1 <= len(raw) <= 50:
        raise ValueError("Benchmark JSON must contain 1–50 cases.")
    cases = []
    for index, item in enumerate(raw):
        if not isinstance(item, dict) or not isinstance(item.get("question"), str) or not item["question"].strip():
            raise ValueError(f"Case {index + 1} needs a question.")
        expected = item.get("expected_citations", [])
        if not isinstance(expected, list) or not all(isinstance(value, str) for value in expected):
            raise ValueError(f"Case {index + 1} expected_citations must be strings.")
        cases.append({"id": str(item.get("id", index + 1))[:100], "question": item["question"][:4000],
                      "expected_citations": expected, "unsupported": bool(item.get("unsupported", False)),
                      "intent_count": item.get("intent_count")})
    return cases


async def run_benchmark(runtime, raw_cases):
    cases = validate_cases(raw_cases); rows = []; started = time.perf_counter()
    supported = emitted = fabricated = trace_events = 0
    valid_ids = {chunk.chunk_id for chunk in runtime.chunks}
    for index, case in enumerate(cases):
        connection = runtime.connection()
        message = make_transcript_message(event_id=f"benchmark-{index}", turn_id=str(uuid4()),
                                          text=case["question"], timestamp_ms=index, is_final=True)
        result = await connection.handle(message)
        citations = result["citations"]
        citation_match = set(citations) == set(case["expected_citations"])
        abstention_match = not citations and bool(result["uncertainty"]) if case["unsupported"] else True
        intent_match = case["intent_count"] is None or len(result["sub_queries"]) == case["intent_count"]
        for claim in result["claims"]:
            if claim["citations"]:
                emitted += 1
                exact = any(claim["text"] == evidence["text"] for evidence in claim["evidence"])
                ids_valid = all(cid in valid_ids and cid in claim["candidate_ids"] for cid in claim["citations"])
                supported += int(exact and ids_valid)
                fabricated += sum(cid not in valid_ids for cid in claim["citations"])
        trace_events += len(connection.telemetry)
        rows.append({"id": case["id"], "question": case["question"], "pass": citation_match and abstention_match and intent_match,
                     "expected_citations": case["expected_citations"], "actual_citations": citations,
                     "intent_count": len(result["sub_queries"]), "uncertainty": result["uncertainty"]})
        await connection.close()
    passed = sum(row["pass"] for row in rows)
    return {"type": "benchmark_result", "scope": "uploaded session corpus", "passed": passed, "total": len(rows),
            "citation_support": {"supported": supported, "emitted": emitted}, "fabricated_ids": fabricated,
            "trace_events": trace_events, "elapsed_ms": round((time.perf_counter() - started) * 1000, 1),
            "cases": rows, "disclosure": "Organizer-supplied labels evaluated locally against this session corpus; not a Samsung-certified score."}
