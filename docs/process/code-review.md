# Code Review Practices

> Part of the [team process docs](../../CONTRIBUTING.md). Back to [README](../../README.md).

Every change reaches `develop` or `main` through a reviewed pull request. Branch rules are in the [Git workflow](git-workflow.md).

## Pull requests

- Open a pull request as soon as the work is ready for review. Use a **draft** pull request if you want early feedback.
- Keep pull requests small, ideally one task each. Large pull requests are slow to review and more likely to hide bugs.
- Work branches (`feature/*`, `fix/*`, etc.) target `develop`. Release and hotfix branches target `main`, followed by a second pull request into `develop`, as described in the [Git workflow](git-workflow.md).
- Fill in the pull request template, including `Closes #<issue-number>`. Note that GitHub only closes the issue automatically when merging into the default branch (`develop`); close it manually otherwise.
- All automated checks (build, tests, linting) must pass.
- At least **one approval** from another team member is required before merging.
- The **author** merges their own work-branch pull request into `develop` after approval, then deletes the branch. Release and hotfix pull requests into `main` are merged by the GitHub Manager (Andrew).
- Changes that affect other services (a new or changed API, a new event format) or the overall architecture also need approval from the Technical Lead (Rayan), and should be discussed with the team before the pull request is opened.
- Merge method: **Squash and merge** for work branches into `develop`, so each task becomes one clean commit. **Create a merge commit** for release and hotfix branches, so `main` and `develop` keep a shared history.

## Reviewing

Reviewers should respond within the times in our [communication protocol](communication.md): 24 hours on weekdays, 1 hour during critical deadlines. If you can't, say so in Discord so someone else can pick it up.

When reviewing, check that:

- The change does what the linked issue and its acceptance criteria require.
- The code is readable, and names explain what things are.
- Tests cover the new behaviour, including error and edge cases.
- No secrets, keys, or personal data are committed.
- Privacy rules are respected: riders' home addresses and drivers' uploaded documents are never sent to other users.
- Service boundaries are respected: a service only reads its own database and talks to other services through their documented APIs or events.
- Documentation (service READMEs, API docs) is updated along with the code.

Comment conventions:

- **blocking:** must be fixed before merging.
- **suggestion:** worth considering, the author decides.
- **nit:** minor style point, optional.
- **question:** asking for understanding, not requesting a change.

## Use of AI in reviews

In line with our [working agreement](working-agreement.md), pull requests are reviewed by people. AI tools may not be used to review pull requests. GitHub Copilot may be used by the author as a secondary check on their own code before requesting review.

## Tone

Review the code, not the person. Explain why you're suggesting a change. The author resolves each comment by fixing it or replying, and re-requests review once done.
