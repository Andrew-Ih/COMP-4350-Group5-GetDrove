# Core Features and Stretch Goals

> Back to [README](../../README.md) · [Sprint 0](../../sprint0.md)

Each core feature is a GitHub issue labelled `feature`. Its user stories, with acceptance criteria, are sub-issues, and stories that need a technical breakdown have development tasks as their own sub-issues. Everything is tracked on the [project board](https://github.com/users/Andrew-Ih/projects/3).

**Totals:** 7 core features · 21 core user stories · 47 core development tasks · 6 stretch goals (live driver tracking keeps its story and 5 tasks under its stretch goal)

## Core features

### Accounts and verification
**Issue:** [#1](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/issues/1)

Signup restricted to UofM email. Riders complete a profile; drivers also upload licence and/or insurance and can't post until approved. Both sides have a visible rating and trip count. Driver and rider are roles on one account, since most students are both at different times.

Stories: Sign up with UofM email · Upload licence and insurance for driver approval

### Trip posting
**Issue:** [#13](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/issues/13)

Drivers post departure time, starting area, destination, and available seats, either as a one-off or a recurring weekday pattern, with the return trip linked. Trips can be edited or cancelled, and accepted riders are notified when that happens.

Stories: Post a trip · Post a recurring weekday trip · Cancel a posted trip

### Route matching
**Issue:** [#21](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/issues/21)

The system works out the driver's actual driving route and shows the trip to students along it, using real road distance rather than straight-line proximity. Riders only see trips that genuinely pass near them.

Stories: Show only trips that pass near the rider · Suggested pickup point on the route

### Requests and acceptance
**Issue:** [#33](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/issues/33)

Riders request a seat. For each request the system calculates how many extra minutes that pickup adds given who's already accepted, and shows the driver that number before they decide. Drivers accept manually or set auto-accept rules like a maximum detour or minimum rider rating. Seats can't be oversold when multiple riders request the last one at once.

Stories: Request a seat on a trip · Detour cost per request · Auto-accept rules · Seats cannot be oversold

### Trip execution
**Issue:** [#51](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/issues/51)

Once a trip fills, the system orders the pickups, gives everyone a pickup point and an ETA, and opens a group chat for the trip. On the day: departure reminders, trip status updates (started, picked up, completed), marking riders as picked up or no-show, and driver confirmation that the trip happened.

Live driver location was moved to the stretch goals after instructor feedback ([ADR 0018](../architecture/adr/0018-live-tracking-as-stretch-goal.md)).

Stories: Trip reminder before departure · Mark riders as picked up or no-show · Trip group chat

### Cost splitting and payment
**Issue:** [#65](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/issues/65)

Each rider's share is based on how far they actually rode, not split evenly. Payment is held when they're accepted and charged once the driver confirms the trip, refunded automatically if it's cancelled. Drivers see what they've earned per trip and over the term.

Stories: See my cost before requesting · Charge only after the trip happens · View driver earnings

### Ratings and safety
**Issue:** [#74](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/issues/74)

Both sides rate each other after a trip. No-shows are recorded and count against auto-accept eligibility. Users can report or block someone, and riders can share trip details and status with someone outside the app.

Stories: Rate the other party after a trip · Exclude repeat no-shows from auto-accept · Report or block a user · Share trip with someone outside the app

## Development tasks

Most stories are a day or two of work and don't need breaking down. Stories that span multiple parts of the system or need more than one person are split into tasks that can be assigned and tracked separately, labelled `frontend` or `backend`. Stories not broken down (rating a trip, reporting or blocking a user, viewing driver earnings, cancelling a trip, and requesting a seat) are small enough for one person to pick up as-is.

[All development tasks](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/issues?q=label%3Atask) · Tasks view on the [project board](https://github.com/users/Andrew-Ih/projects/3)

## Stretch goals

These support the vision but are **not part of the core scope**. They're labelled `stretch`, kept in the Backlog, and only started once the core work for a sprint is done. [All stretch goals](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/issues?q=label%3Astretch)

- **Live rerouting.** The driver is already en route and a rider cancels, or traffic closes a street. The system recomputes the pickup order mid-trip and pushes updated ETAs to everyone still waiting.
- **Schedule-based suggestions.** Students enter their class timetable once and the system tells them which recurring trips fit their whole semester, instead of hunting for a ride every night.
- **Cancellation recovery.** A driver cancels at 7am and the system finds the stranded riders another trip leaving nearby with a free seat before they even realize they're stuck.
- **Live driver tracking.** Riders watch the driver's position on a map in real time, with a stale-data indicator if the connection drops. Moved from core scope after instructor feedback: it needs real-time connections and background location, which suit a mobile app better than a website. Its story and tasks are already written and sit under this stretch goal.
- **Native mobile app.** Push notifications that actually work, background location (which would make live driver tracking reliable), and a faster experience than a web app on a phone in winter.
- **Driver reliability scoring.** Learn from trip history which drivers actually show up and arrive on time, and factor that into what riders see rather than relying only on star ratings people rarely leave.
