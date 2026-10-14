# ADR 0008: OSRM as the routing engine

- **Status:** Accepted
- **Date:** 2026-10-04

## Context

The Routing service computes driving routes, road-network corridor matches, walking times to pickup points, snapped pickup points on drivable roads, and detour quotes (target under 1 second). It must be self-hosted.

## Options considered

- **OSRM:** Very fast (C++); `route`, `table`, and `nearest` services; one instance per profile.
- **GraphHopper:** Java; can embed in the service; one instance for several profiles; more limited open-source matrix.
- **Valhalla:** Flexible, heavier to set up.
- **Hosted APIs (Mapbox, Google, OpenRouteService):** No setup; quotas and costs; not self-hosted.

## Decision

Use **OSRM**, with two instances (**car** and **foot** profiles) built from a Winnipeg-clipped OpenStreetMap extract by `infra/osrm/prepare.sh`. **GraphHopper is the backup** if the Sprint 1 spike finds OSRM unsuitable (e.g. no ARM support).

## Consequences

**Positive**

- `table` gives the duration matrix for cheapest-insertion detours in one call; `nearest` snaps pickup points to roads.
- Fastest option, supporting the detour-quote target.
- Winnipeg's extract is small, so two instances are cheap.

**Negative / trade-offs**

- Map data must be preprocessed and isn't committed to the repo.
- Two extra containers to run and keep healthy.
