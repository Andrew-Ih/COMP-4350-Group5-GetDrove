# GetDrove

**GetDrove gives UofM students a seat that's actually theirs.**

GetDrove is a carpooling platform for University of Manitoba students commuting to the Fort Garry campus. Drivers post their commute, the system works out their real driving route and shows the trip to students along it, and drivers see how many extra minutes each rider would add before accepting. Riders get a confirmed seat, a private pickup point, a live ETA, and a fair share of the cost based on how far they rode. Every user is a verified UofM student.

> **Sprint 0:** see [sprint0.md](sprint0.md) for this milestone's planning and setup work.

## Core features

Each feature links to its GitHub issue, which contains its user stories and acceptance criteria. Full descriptions and stretch goals: [Core features](docs/product/core-features.md).

| Feature | Summary |
|---|---|
| [Accounts and verification](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/issues/1) | UofM-email signup; drivers upload licence and insurance and are approved before posting |
| [Trip posting](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/issues/13) | One-off or recurring weekday trips with departure time, route, and seats |
| [Route matching](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/issues/21) | Riders only see trips whose real driving route passes near them; private pickup points |
| [Requests and acceptance](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/issues/33) | Seat requests with the detour cost shown to the driver, auto-accept rules, no overselling |
| [Trip execution](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/issues/51) | Reminders, live driver location, pickup and no-show tracking, trip group chat |
| [Cost splitting and payment](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/issues/65) | Distance-based cost shares, payment held on acceptance and charged after the trip |
| [Ratings and safety](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/issues/74) | Mutual ratings, no-show tracking, report and block, trip sharing links |

[Project board](https://github.com/users/Andrew-Ih/projects/3) · [User stories](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/issues?q=label%3Auser-story) · [Development tasks](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/issues?q=label%3Atask) · [Stretch goals](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/issues?q=label%3Astretch)

## Team: Code Bros

| Name | GitHub | Team role |
|---|---|---|
| Chimdindu Iwuchukwu (Chimdi) | [@chimd111](https://github.com/chimd111) | Project Coordinator |
| Andrew Ihenacho | [@Andrew-Ih](https://github.com/Andrew-Ih) | GitHub Manager |
| Daniel Nwogo | [@nigerianpickle](https://github.com/nigerianpickle) | Documentation Lead |
| Farouk Amusat (Fola) | [@Folariin](https://github.com/Folariin) | Task Leader |
| Kelvin Enobie | [@KelzIv](https://github.com/KelzIv) | Quality Checker |
| Rayan Kashif | [@RayanKashif69](https://github.com/RayanKashif69) | Technical Lead |

Everyone is a developer; these roles are additional responsibilities. See the [working agreement](docs/process/working-agreement.md).

## Documentation

**Product**

- [Product vision and customer context](docs/product/vision.md)
- [Core features and stretch goals](docs/product/core-features.md)
- [Non-functional expectations](docs/product/non-functional.md)

**Architecture**

- [Technology stack](docs/architecture/tech-stack.md)
- [Architecture](docs/architecture/architecture.md)

**Team process**

- [Working agreement](docs/process/working-agreement.md)
- [Communication protocol](docs/process/communication.md)
- [Planning practices](docs/process/planning.md)
- [Git workflow](docs/process/git-workflow.md)
- [Coding standards](docs/process/coding-standards.md)
- [Code review practices](docs/process/code-review.md)

## Sprints

- [Sprint 0: Planning and setup](sprint0.md)

## Getting started

The whole system will run locally with a single Docker Compose command. Setup instructions will be added here once the first services exist.
