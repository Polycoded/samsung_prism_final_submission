"""CiteFrontier validation prototype.

The package deliberately keeps routing, citation checks, session state, and
telemetry explicit so they can be evaluated against the Streaming Live RAG
guide. It does not use agents or persistent conversation checkpoints.
"""

from .engine import CiteFrontierEngine
from .models import Decision, TranscriptEvent

__all__ = ["CiteFrontierEngine", "Decision", "TranscriptEvent"]
