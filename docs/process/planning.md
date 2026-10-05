# Planning Practices

> Part of the [team process docs](../../CONTRIBUTING.md). Back to [README](../../README.md).

## Iterations

- Iteration length and dates follow the course schedule. Each sprint's dates are recorded on its milestone and its `sprintN.md` page once announced.
- Each iteration has a GitHub milestone (`Sprint 0`, `Sprint 1`, …). Issues planned for that iteration are assigned to its milestone.
- We aim to start each sprint early and finish its work 2–3 days before the deadline, leaving time for review, fixes, and the release.
- **Sprint planning** at the start of each iteration: the team reviews the Backlog, agrees which issues move to Todo, and assigns owners.
- **Retrospective** at the end of each iteration: what went well, what didn't, and what we'll change. Changes to our process are made by updating these documents.

## Distributing work

- Work is assigned through GitHub Issues. At sprint planning, each member takes on issues for the iteration and assigns themselves.
- We aim for everyone to contribute equally, so the team checks at planning that the work is balanced across members.
- Each backend service has an owner who is responsible for it end to end and chooses the tools used inside it. Other members still contribute to any service; the owner reviews changes to it.

Provisional owners, based on each member's individual goals. The team will confirm or change these before Sprint 1 development begins.

| Service | Owner |
|---|---|
| Accounts | Fola |
| Trips | Andrew |
| Routing | Rayan |
| Payments | Chimdi |
| Notifications | Daniel |
| Web app (frontend) | Kelvin |

- The Task Leader (Fola) reminds members of upcoming due dates, and the Project Coordinator (Chimdi) tracks deadlines and organises meetings. See the [working agreement](working-agreement.md).

## Coordinating dependencies

- Many stories cross service boundaries (for example, requesting a seat involves Trips, Routing, Payments, and Notifications). Before building, the owners involved agree on the API or event format and document it in the providing service's README.
- Any change that affects another service is discussed with the team first.
- If an issue can't start until another is finished, note it in the issue ("Blocked by #42") and raise it at the next meeting.
- Frontend and backend work can proceed in parallel: once an API is agreed, the frontend builds against a stub or mock until the real endpoint is ready.

## Integrating contributions

All work is integrated through pull requests into `develop`, reviewed by at least one teammate, with CI checks passing. At the end of each iteration, `develop` is released to `main` through a release branch. See the [Git workflow](git-workflow.md) and [code review practices](code-review.md).

## Adapting assignments

- Assignments and roles are revisited at the start of each sprint.
- If someone's workload or availability changes, or an issue has had no progress and the owner hasn't responded within our expected response times, the team reassigns it by agreement and records the change in the meeting notes.
- If something turns out larger than expected, it's split into smaller tasks; if we're behind, lower-priority stories move back to the Backlog. Stretch goals are only started once core work for the sprint is done.

## Tracking work

All work is tracked in the [GetDrove project board](https://github.com/users/Andrew-Ih/projects/3).

- **Features** are parent issues labelled `feature`. Each contains its user stories as sub-issues.
- **User stories** are labelled `user-story` and list their acceptance criteria as a checklist.
- **Tasks** are labelled `task` plus `frontend` or `backend`, and are sub-issues of the story they belong to.
- **Area labels** (`accounts`, `trip-posting`, `routing`, `requests`, `trip-execution`, `payments`, `ratings-safety`) show which part of the system an issue belongs to.

The project has three views:

| View | Layout | Used for |
|---|---|---|
| **Board** | Kanban board | Day-to-day progress. Each card moves across the columns below as work happens. |
| **Plan** | Table grouped by feature | The overall structure: each feature with its user stories underneath. |
| **Tasks** | Table grouped by story | Dividing up work: every task with its `frontend`/`backend` label and assignee. |

Board columns and what they mean:

| Status | Meaning |
|---|---|
| Backlog | Planned but not scheduled for the current iteration (including stretch goals) |
| Todo | Scheduled for the current iteration and ready to be picked up |
| In Progress | Someone is assigned and actively working on it |
| In Review | A pull request is open and waiting for review |
| Done | Merged into `develop` and meets the Definition of Done |

Rules:

- At the start of each iteration, the team agrees which issues move from Backlog to Todo.
- Assign yourself to an issue before starting it, and move it to In Progress.
- When you open a pull request for it, move the issue to In Review. If changes are requested, it stays in In Review until the pull request is merged.
- Don't work on something that has no issue. If it's needed, create the issue first.
- Small stories with no tasks are worked on directly; larger ones are worked on task by task.
- When all of a story's acceptance criteria are checked off, close the story.

## Estimation

Each issue is sized S, M, or L in the project's Size field: S is under half a day, M is about a day, and L is two or more days. L stories are split into development tasks.

## Definition of Done

In our working agreement, a task is done when the team approves it by consensus. In practice, that approval is given through the review process, and an issue is done when:

An issue is done when:

- [ ] The code is merged into `develop` through an approved pull request
- [ ] All acceptance criteria (for stories) are met and checked off
- [ ] Tests are written and passing
- [ ] Linting and formatting pass
- [ ] Any new setup steps or environment variables are documented in the README
