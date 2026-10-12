"""Naming shared by producers and consumers."""

# Field in each Redis Streams entry that holds the envelope as JSON.
ENVELOPE_FIELD = "envelope"


def stream_name(producer: str) -> str:
    """Each producing service has one stream, e.g. ``events.accounts``."""
    return f"events.{producer}"
