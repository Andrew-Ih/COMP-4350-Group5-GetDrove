# Non-Functional Expectations

> Back to [README](../../README.md) · [Sprint 0](../../sprint0.md)

These are our initial expectations for how GetDrove should behave. They will be refined in later sprints, and some will be tested directly (for example, through load tests).

## Performance

- **Detour quotes return in under 1 second.** A driver reviewing requests is waiting on this, so it's the one path that can't feel slow.
- Most screens are simple database reads and should load in under 1 second.
- Route computation for a newly posted trip finishes within 3 seconds.

## Scalability

- Baseline target: 500 registered users and 100 posted trips per day.
- Load test target: 50 concurrent users sustained for 5 minutes without errors or timeouts.
- The Routing service is the bottleneck, since route computation is the most expensive operation. Load tests target it specifically.
- Real traffic is bimodal, mostly 7:00–8:30am and 3:30–5:30pm, so the system has to handle spikes rather than steady load.

## Reliability

- If Notifications is down, trips still run, and messages are delivered when it recovers.
- If Routing is down, accepted trips are unaffected, and new quote requests fail with a clear error instead of hanging.
- Failed requests return meaningful error messages, never a blank 500.

## Security and privacy

- Signup is restricted to verified @myumanitoba.ca addresses.
- All API endpoints except signup and login require a valid token.
- Home addresses are never returned to other users. Riders get a pickup point on the route; drivers see the pickup point, not the residence.
- No real card data touches our systems (Stripe test mode).
- Automated dependency vulnerability scanning runs in CI.

## Maintainability and testability

- Each service owns its own database and doesn't read another service's data directly.
- Services talk to each other through documented APIs.
- Tests run automatically in CI on every pull request, aiming for around 70% coverage on core logic.
- The whole system runs locally with a single Docker command.

## Usability and accessibility

- A driver can post a trip in under 60 seconds.
- A rider goes from opening the app to requesting a seat in three interactions or fewer.
- Mobile-first. GetDrove gets used standing outside in winter, on a phone, with gloves on: large touch targets, high contrast, and no small text.
