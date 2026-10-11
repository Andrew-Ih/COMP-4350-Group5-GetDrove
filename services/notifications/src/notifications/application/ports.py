"""Ports: the interfaces (``typing.Protocol``) that use cases need from the outside world.

Adapters implement these, and tests use in-memory fakes. Example:

    class TripRepository(Protocol):
        async def add(self, trip: Trip) -> None: ...
"""
