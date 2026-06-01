# Phase 160 — Docker Containerization (Optional / Deferred)

**Status:** DEFERRED — optional hardening. Do not start without explicit instruction.

## Why

Once the app is exposed to the internet (Phase 135), the two standing worries are
(1) an attacker compromising the prod **server** and (2) pivoting into the home
**network**. Running the API in a **hardened container** is a strong mitigation for
worry (1): an application-layer RCE only lands the attacker *inside the container*;
reaching the host then requires a separate, much rarer **container-escape**. That is a
qualitatively stronger boundary than running `dotnet run` as a (even least-privilege)
host account, where an RCE puts the attacker directly on the host.

On **Windows** the isolation is arguably even stronger: Docker Desktop runs Linux
containers inside a WSL2/Hyper-V VM, so the chain to the Windows host is
container → escape container → escape VM → host (two boundaries).

**What it does NOT solve:** worry (2), the network. The host is still on the LAN, so a
host compromise (or an unrestricted container network) can still reach other devices.
Network blast-radius is a **router/VLAN** concern (isolate the box on a guest network /
DMZ subnet), independent of Docker.

## Scope

- **Dockerfile for the C# API** (multi-stage build; publish to a runtime image).
- Serve the built UI from the API as today (Option B is unchanged inside the container).
- **MySQL decision:** keep MySQL on the host (container connects to host DB) **or**
  containerize it with a persistent named volume for the data dir. Document the
  data-migration path if containerizing.
- **Attachments dir** (`E:\fedprospector\attachments`, `ATTACHMENT_DIR`): bind-mount as
  a volume.
- **Config:** the external config file (`C:\fedprospector\config\fedprospector.local.json`)
  and the cert `.pfx` are bind-mounted read-only; `FEDPROSPECTOR_CONFIG` points at the
  mounted path. JWT still via env var (passed to the container, not baked into the image).
- **`deploy.ps1` changes:** build the image (or `docker compose build`) instead of/along
  with shipping source; restart the container on prod.

## Hardening requirements (the isolation is only as strong as the config)

The "hard to escape" property is **forfeited** by common misconfigurations. Require:

- **Non-root** user inside the container (`USER` in the Dockerfile, not root).
- **`--read-only`** root filesystem (+ explicit writable `tmpfs`/volumes where needed).
- **`--cap-drop ALL`** (add back only what's strictly required) and `--security-opt no-new-privileges`.
- **No `--privileged`.**
- **Do NOT mount the Docker socket** (`/var/run/docker.sock`) into the container.
- **No `--network host`;** use a restricted bridge network and publish only the one port.
- Pin/patch the base image; rebuild on CVE updates.

## Prerequisites / cost to weigh

- Docker Desktop + WSL2 on the Windows prod box (another component to run/patch;
  licensing is free for personal/small use).
- Reworking the native `fed_prospector.bat` start/stop + robocopy deploy model around
  images/volumes; MySQL data and volume-performance considerations on Windows/WSL2.

## Decision note

For 3 trusted users on a working Windows-native stack, this is a *stronger* server-
containment option than the least-privilege host account, at a higher operational cost.
Strongest motivation arrives if the deployment ever moves to a **Linux** host (native
containers, no Desktop/WSL2 layer). Pair with router-level network segmentation for the
network worry regardless.

## Related

- Phase 135 — Public Internet Exposure (single-port HTTPS) — the exposure this hardens.
- `thesolution/reference/14-PRODUCTION-EXPOSURE.md` — current exposure model + runbook.
