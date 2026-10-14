# ADR 0016: Google Cloud VM, live site deployed from main

- **Status:** Accepted
- **Date:** 2026-10-10
- **Supersedes:** [ADR 0007](0007-hosting-and-environments.md)

## Context

[ADR 0007](0007-hosting-and-environments.md) chose an Oracle Cloud Always Free ARM VM, with the AWS Free plan as backup, and deployed the live site from `develop`. Two things changed:

1. **Hosting.** Oracle returned "Out of capacity" for the Ampere A1 shape in the Canadian region, including at the smaller 1 OCPU / 6 GB size. The AWS Free plan was not available, because its credits only apply to AWS accounts created after mid-2025. Google Cloud's free trial was available: about US$300 (CA$425) of credit for 90 days, which covers the rest of the term, and the account is not charged when the trial ends unless it is manually upgraded.
2. **Deploy branch.** The team wants the live site, which the instructor evaluates, to show only reviewed, released code rather than every merge in progress. The Sprint 2 rubric still requires that changes to the main development branch take part in an automated delivery or deployment workflow.

The stack still needs about 4 GB of RAM and several always-running processes, so a VM with Docker Compose remains the right shape.

## Options considered

- **Keep retrying Oracle:** free, but capacity could take days or weeks to free up.
- **AWS Free plan:** not available for our account.
- **Google Cloud free trial VM:** available now; credit covers the term; x86 machines.
- **Student credits (GitHub Student Developer Pack, Azure for Students):** viable, but approval takes days.
- **Paid VPS:** reliable but not free.
- **Deploy the live site from `develop`** (as in ADR 0007): fastest feedback, but the evaluated site changes with every merge.
- **Deploy the live site from `main`:** the live site only changes on releases and hotfixes; `develop` still gets automated delivery.

## Decision

**Hosting:** a **Google Cloud Compute Engine** VM, paid for by the free-trial credit:

| Setting | Value |
|---|---|
| Machine | e2-standard-2 (2 vCPU, 8 GB RAM, x86-64) |
| Region / zone | northamerica-northeast2 (Toronto), zone c |
| OS | Ubuntu 24.04 LTS (amd64) |
| Disk | 40 GB balanced persistent disk, with the default daily snapshot schedule |
| IP address | Static external IP (`getdrove-ip`) |
| Firewall | SSH (22), HTTP (80), HTTPS (443) |
| Runtime | Docker Engine and Docker Compose |

Images are built for **`linux/amd64`** in GitHub Actions.

**Branches and environments:** one live environment, deployed from **`main`**:

- **Every merge to `develop`** runs the full CI suite, then builds the Docker images and publishes them to GitHub Container Registry tagged with the commit SHA (**continuous delivery**). This is the automated workflow for our main development branch.
- **Every merge to `main`** (a release or hotfix) deploys those images to the live VM and runs a smoke test (**continuous deployment**).
- **Every release tag** on `main` (`vX.Y.Z`) also publishes versioned images to DockerHub.
- We release at the end of each sprint at minimum, and more often when a set of stories is ready (for example, before a demo meeting).

## Consequences

**Positive**

- Works today, with no capacity lottery.
- x86 images match our laptops and GitHub's default runners, so builds are simpler than ARM.
- The live site the instructor sees only ever contains reviewed, released code, and every live version matches a tag on `main`.
- Rolling back is simple: redeploy the previous release tag.

**Negative / trade-offs**

- Not free indefinitely: the trial ends about 90 days after 2026-10-10 (early January 2027). The VM costs about US$58/month plus a static IP and snapshots, roughly US$200 of the credit over the trial. After the term the VM is shut down, or moved elsewhere if the project continues.
- 8 GB of RAM instead of 12 GB; still about twice what the stack needs.
- The live site lags behind `develop` until the next release, so releases must happen often enough for demos and for the instructor to see current work.
- We maintain one server (OS updates, disk, backups). Ubuntu's automatic security updates and the snapshot schedule reduce this.
