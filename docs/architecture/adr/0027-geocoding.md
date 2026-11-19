# ADR 0027: Typed addresses are looked up with OpenStreetMap's Nominatim, through Routing

- **Status:** Proposed
- **Date:** 2026-11-18

## Context

Riders and drivers choose their area by tapping the map or sharing their location. Testing the live site after Sprint 1 showed that's hard for someone who doesn't know the map or blocks location access ([#257](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/issues/257), Sprint 1 retro). They should be able to type an address or a place name instead.

Turning text into a point needs a geocoder; our map tiles (OpenFreeMap) and OSRM can't do it. What mattered:

- **Privacy.** A rider's typed address is used for the search only and never saved, and a driver's trip keeps storing a neighbourhood label, never a street address (#257). The fewer places a typed address goes, the better.
- **Cost and keys.** No budget, and an API key must never reach the browser.
- **Winnipeg only.** Results must be inside the area our routing engine's map covers (the OSRM `BBOX`).
- **No suggestions while typing.** The team decided a user types, presses Search and picks from a few matches. That keeps the number of lookups low, and it decides which services are allowed.

## Options considered

- **Nominatim (OpenStreetMap Foundation's public server):** free, no key, the same OpenStreetMap data as our map and routes. Its [usage policy](https://operations.osmfoundation.org/policies/nominatim/) allows searches users trigger themselves at moderate volume, at most 1 request per second for the whole application, with an identifying User-Agent, caching, and attribution. It forbids autocomplete, which we don't need. House-number coverage depends on what's mapped in OpenStreetMap; a missing number falls back to the street.
- **Photon (komoot's public server):** good for autocomplete, but its maintainer says the public server is [for demos and testing only](https://lists.openstreetmap.org/pipermail/photon/2023-June/000209.html), with no availability guarantee.
- **Geoapify:** a commercial API built on OpenStreetMap and open address data, with autocomplete. Free plan: 3,000 requests a day and 5 a second, commercial use allowed, with a "Powered by Geoapify" link ([pricing](https://geoapify.com/pricing)). Needs an account and a key in GitHub Secrets, and typed addresses go to another company.
- **Self-hosting** (Nominatim, Photon, or open address data in PostGIS): no third party and no limits, but an import pipeline, gigabytes of data and memory on our one VM, and days of work. Too much for the value right now.

## Decision

**Routing looks typed addresses up with the public Nominatim server**, through a new public endpoint, `POST /api/routing/places` (contract in `contracts/openapi/routing.json`):

- The browser sends `{ "query": "750 Osborne St" }` to Routing, never to Nominatim directly. It's a **POST**, so the address is never in one of our URLs or logs. Routing doesn't store or log it.
- Routing asks Nominatim with our User-Agent, **bounded to the OSRM map's area** (`viewbox` with `bounded=1`), in Canada, at most 5 results. It drops anything outside the area and returns `{ label, lat, lng }` for each match. An empty list means nothing matched.
- **At most 1 request a second** to Nominatim for the whole service, as the policy says. A request that would wait too long gets `503 geocoding_unavailable`, and the user can still tap the map.
- **A small in-memory cache** answers repeated searches without asking Nominatim again, as the policy asks. It lives only in the service's memory, is never written anywhere, and entries expire after an hour.
- The map already credits OpenStreetMap, which covers attribution.
- Picking a match works exactly like tapping the map: the rider's search still sends only the point, and a driver's trip still saves the neighbourhood label.

Behind a port (`PlaceFinder`), so switching to Geoapify or a self-hosted geocoder later only replaces one adapter and a setting.

## Consequences

**Positive**

- Free, with no key to manage and nothing new to host.
- Typed addresses go only to the OpenStreetMap Foundation, under its privacy policy, and are never stored by us.
- Same data as the map and the routes, so a place you can find is a place we can route to.

**Negative / trade-offs**

- 1 request per second for everyone is fine for a class project's traffic, but a busy moment could make someone wait or see "try again". The cache helps with repeated searches. More traffic would mean moving to Geoapify or self-hosting.
- No availability guarantee: if Nominatim is down, typing an address doesn't work, and tapping the map or sharing your location still does.
- Some Winnipeg house numbers may be missing from OpenStreetMap; the street or place is found instead, which is close enough to choose an area.
- No suggestions while typing, which the policy forbids. If the team wants them later, that means Geoapify or self-hosting, and a new ADR.
