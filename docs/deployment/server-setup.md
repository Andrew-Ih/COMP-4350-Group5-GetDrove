# Server Setup (Google Cloud)

> Back to [README](../../README.md) · Decision: [ADR 0016](../architecture/adr/0016-google-cloud-hosting-and-deploy-from-main.md)

This guide records how the production server for GetDrove was set up, so anyone on the team can understand it, maintain it, or rebuild it. It covers the server only. Deploying the application to it is done by GitHub Actions (see [Deploying](#deploying-the-application)).

**Never commit secrets.** Private keys, passwords, and API keys go in GitHub Actions secrets or the server's `.env` file, never in this repository.

## Summary

| Item | Value |
|---|---|
| Provider | Google Cloud Platform (Compute Engine), free-trial credit |
| Project | `getdrove` |
| VM name | `getdrove-prod` |
| Machine type | e2-standard-2 (2 vCPU, 8 GB RAM, x86-64) |
| Region / zone | `northamerica-northeast2` (Toronto), zone `northamerica-northeast2-c` |
| Operating system | Ubuntu 24.04 LTS (amd64) |
| Boot disk | 40 GB balanced persistent disk, daily snapshot schedule (`default-schedule-1`) |
| External IP | `34.130.160.109`, reserved as static IP `getdrove-ip` |
| Open ports | 22 (SSH), 80 (HTTP), 443 (HTTPS) |
| Server user | `andrew` |
| App folder | `/opt/getdrove` |
| Software | Docker Engine, Docker Compose plugin |
| Domain / HTTPS | Not set up yet (see [Next steps](#next-steps)) |
| Owner | Andrew (GitHub Manager) |

**Cost:** about US$58/month for the VM and disk, plus a few dollars for the static IP and snapshots, paid from the trial credit (about US$300 / CA$425 for 90 days, from 2026-10-10 until early January 2027). Remaining credit is shown under **Billing → Overview**. When the trial ends, Google does not start charging unless the account is manually upgraded.

## 1. Project and budget

1. In the Google Cloud console, create a project named `getdrove` and select it.
2. **Billing → Budgets & alerts → Create budget** with alerts at 50%, 90%, and 100%, to track how fast the credit is used.

## 2. SSH key

Create a key on your own computer (macOS/Linux):

```bash
ssh-keygen -t ed25519 -f ~/.ssh/getdrove_oci -C "getdrove-oci"
cat ~/.ssh/getdrove_oci.pub
```

Google Cloud uses the **last word** of a public key as the Linux username, so before adding a key to Google Cloud, change the last word to the username you want (for example, replace `getdrove-oci` with `andrew`).

## 3. Create the VM

**Compute Engine → VM instances → Create instance** (enable the Compute Engine API if asked):

| Section | Setting |
|---|---|
| Name | `getdrove-prod` |
| Region | `northamerica-northeast2` (Toronto) |
| Machine configuration | General purpose → E2 → `e2-standard-2` |
| OS and storage → Change | Ubuntu, **Ubuntu 24.04 LTS** (x86/64, not Minimal or Arm64), balanced persistent disk, **40 GB** |
| Networking | Tick **Allow HTTP traffic** and **Allow HTTPS traffic** |
| Security → SSH keys | Add the public key from step 2 (last word changed to `andrew`) |

The default snapshot schedule is left on, so the disk is backed up daily.

## 4. Reserve a static IP

By default the external IP is ephemeral and can change if the VM stops.

1. **VPC network → IP addresses**.
2. On the row for the VM's **external** address, open **⋮ → Promote to static IP address**, name it `getdrove-ip`.

`getdrove-ip` is only a label inside Google Cloud; always connect with the IP address itself.

## 5. Log in

```bash
ssh -i ~/.ssh/getdrove_oci andrew@34.130.160.109
```

The **SSH** button next to the VM in the console is a fallback that works from the browser.

## 6. Update the system and install Docker

On the server:

```bash
sudo apt update && sudo apt upgrade -y
sudo timedatectl set-timezone America/Winnipeg

curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker andrew
```

Log out (`exit`) and back in so the `docker` group applies, then check:

```bash
docker run --rm hello-world
docker compose version
```

Ubuntu installs security updates automatically by default. If an upgrade asks for a restart, run `sudo reboot` and log in again after a minute.

Unlike some providers' images, Google's Ubuntu image has no extra firewall rules on the server itself; the VM's **Allow HTTP/HTTPS traffic** firewall settings are enough.

## 7. Check the server is reachable

```bash
docker run -d --name test -p 80:80 nginx
```

Open `http://34.130.160.109` in a browser and look for "Welcome to nginx!", then remove the test container:

```bash
docker rm -f test
```

## 8. Deploy key for GitHub Actions

GitHub Actions logs in with its own key, separate from anyone's personal key.

On your computer:

```bash
ssh-keygen -t ed25519 -f ~/.ssh/getdrove_deploy -N "" -C "github-actions-deploy"
cat ~/.ssh/getdrove_deploy.pub
```

Add the public key in the console: **VM instances → getdrove-prod → Edit → SSH Keys → Add item**, paste the key with its last word changed to `andrew`, then **Save**. Keys added through the console are managed by Google and won't be removed.

Test it from your computer (not from the server):

```bash
ssh -i ~/.ssh/getdrove_deploy andrew@34.130.160.109 "echo deploy key works"
```

Create the app folder on the server:

```bash
sudo mkdir -p /opt/getdrove && sudo chown andrew:andrew /opt/getdrove
```

Add these repository secrets in **GitHub → Settings → Secrets and variables → Actions**:

| Secret | Value |
|---|---|
| `DEPLOY_HOST` | `34.130.160.109` |
| `DEPLOY_USER` | `andrew` |
| `DEPLOY_SSH_KEY` | The full **private** key `~/.ssh/getdrove_deploy`, including the `BEGIN`/`END` lines |

## Deploying the application

Deployment is automated by GitHub Actions: every merge to `main` (a release or hotfix) builds the images, copies the production Compose file and `.env` to `/opt/getdrove` with the deploy key, runs `docker compose pull && docker compose up -d`, and runs a smoke test. How it works, the secrets it needs and how to roll back: **[Deployment](deployment.md)**.

## Maintenance

| Task | How |
|---|---|
| Check the app is running | `docker compose -f /opt/getdrove/docker-compose.prod.yml ps` |
| View a service's logs | `docker compose -f /opt/getdrove/docker-compose.prod.yml logs -f trips` |
| Check disk space | `df -h` (clean old images with `docker image prune -a` if it gets full) |
| Check memory | `free -h` |
| Roll back | Run the Deploy workflow with an earlier commit's images ([Deployment](deployment.md#5-rolling-back)) |
| Restore from backup | **Compute Engine → Snapshots**, create a disk from the latest snapshot |
| Give a teammate server access | Add their public key in **VM → Edit → SSH Keys** (no Google Cloud account access needed) |
| Check remaining credit | **Billing → Overview** |

## Troubleshooting

| Problem | Cause and fix |
|---|---|
| `Could not resolve hostname getdrove-ip` | `getdrove-ip` is a Google Cloud label, not a hostname. Use `34.130.160.109`. |
| `Permission denied (publickey)` | The key wasn't added, or its last word isn't `andrew`. Add it through **VM → Edit → SSH Keys**. Run SSH commands from your own computer, not from inside the server. |
| `permission denied` running `docker` | Log out and back in after `usermod -aG docker andrew`. |
| Site not reachable on port 80/443 | Check **Allow HTTP/HTTPS traffic** is ticked on the VM (**Edit → Networking**). |

## Next steps

- **Domain and HTTPS:** Let's Encrypt can't issue certificates for a bare IP. Before demos, point a domain at the static IP (a free DuckDNS subdomain, or `34-130-160-109.sslip.io` with no signup) and let Traefik obtain the certificate.
- **After the term:** stop or delete the VM and release the static IP so nothing is charged, unless the project continues elsewhere.
