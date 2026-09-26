"""Small shared constructor that avoids a server/benchmark import cycle."""
def make_transcript_message(**values):
    from .server import TranscriptMessage
    return TranscriptMessage(**values)
