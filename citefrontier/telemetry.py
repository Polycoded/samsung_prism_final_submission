"""Local structured telemetry required by Theme 4 G6."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from .models import TraceEvent


class TelemetryRecorder:
    def __init__(self) -> None:
        self.events: list[TraceEvent] = []

    def record(self, event_type: str, timestamp_s: float, session_id: str, **payload: object) -> None:
        self.events.append(TraceEvent(event_type, timestamp_s, session_id, dict(payload)))

    def by_type(self, event_type: str) -> tuple[TraceEvent, ...]:
        return tuple(event for event in self.events if event.event_type == event_type)

    def write_jsonl(self, path: Path) -> None:
        with path.open("w", encoding="utf-8") as handle:
            for event in self.events:
                handle.write(json.dumps(asdict(event), sort_keys=True) + "\n")
