"""Application layer: use cases, plus the ports (Protocols) they depend on.

Depends only on the domain layer. Everything external (database, other services,
the broker, email, Stripe) is reached through a port defined in ``ports.py``.
"""
