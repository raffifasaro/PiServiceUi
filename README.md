# PiServiceUi

A tiny, password-protected service host for a **Raspberry Pi Zero W**. It runs your
small services (mainly Python Discord bots) as managed subprocesses, and gives you a
web UI to **start / stop / restart** them and watch **health & performance metrics**.

- **Left sidebar** — live host metrics (CPU, memory, disk, temperature, load, uptime).
- **Main grid** — one widget card per service with status, CPU/RAM/uptime, controls and logs.
- **Slot in a bot** — drop a folder with a `service.yaml` into `services/` and click *Rescan*.

The host itself runs in Docker; each service runs as a child process inside its own
virtualenv (`data/venvs/<name>`), so dependencies never collide.

---

## How it fits together

```
Browser ──LAN──> FastAPI (uvicorn, in Docker)  ── serves the built React SPA
                       │  REST + SSE (cookie-auth)
                       ▼
                 ServiceManager ──spawns──> bot subprocess (own venv)  …
                       │  psutil per-PID + host metrics
```

| Piece | Tech |
|------|------|
| Backend | FastAPI + uvicorn, `psutil`, `passlib` (pbkdf2), `itsdangerous` sessions |
| Frontend | React + Vite + TypeScript (built to static, served by the backend) |
| Services | discovered from `services/*/service.yaml`, run via per-service venv |

---

## Add a service

```
services/
  my-bot/
    service.yaml
    bot.py
    requirements.txt   # optional
    .env               # optional (DISCORD_TOKEN=...)
```

`service.yaml`:

```yaml
name: my-bot
description: "My Discord bot"
entrypoint: bot.py          # a .py file, or a module path like "package.module"
requirements: requirements.txt
env_file: .env
autostart: false            # start when the host boots
restart: on-failure         # never | on-failure | always
```

See `services/sample-bot/` for a working, token-free example. After adding a folder,
click **Rescan** in the UI (no restart needed).

---

## Set a password

The UI uses a single password stored as a hash. Create your `.env`:

```bash
cp .env.example .env
python scripts/hash-password.py            # paste the output into UI_PASSWORD_HASH
python -c "import secrets; print(secrets.token_hex(32))"   # SESSION_SECRET
```

---

## Local development (Windows / Mac / Linux)

Two terminals. **Backend:**

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1        # Windows; use `source .venv/bin/activate` elsewhere
pip install -r requirements.txt
copy .env.example .env              # then fill UI_PASSWORD_HASH + SESSION_SECRET
python -m uvicorn app.main:app --reload --port 8080
```

**Frontend** (Vite proxies `/api` to the backend, so it's one origin):

```powershell
cd web
npm install
npm run dev
```

Open http://localhost:5173, log in, and start/stop `sample-bot`. Watch its CPU/RAM and
uptime tick in the card and the host meters in the sidebar; open **Logs** to tail output.

> On non-Linux dev machines, host CPU temperature shows `—` (no `/sys` thermal zone) and
> process termination uses `terminate()` instead of POSIX signals — both expected.

---

## Deploy on the Raspberry Pi (Docker + tmux)

The Pi Zero W is **ARMv6**, so build the image on your dev machine with buildx and the
explicit platform, then run it on the Pi. React is built inside the image's build stage
on your machine — nothing heavy compiles on the Pi.

```bash
# On your dev machine (one-time): enable buildx emulation
docker buildx create --use

# Build for the Pi and load/push the image
docker buildx build --platform linux/arm/v6 -t piserviceui:latest --load .
# (or --push to a registry the Pi can pull from)
```

On the Pi:

```bash
git clone <your-repo> piserviceui && cd piserviceui
cp .env.example .env        # set UI_PASSWORD_HASH + SESSION_SECRET
# drop your bot folders into services/
bash scripts/start-tmux.sh  # docker compose up -d + attachable `logs -f` in tmux
```

Browse to `http://<pi-ip>:8080`. Detach tmux with `Ctrl-b d`; re-attach with
`tmux attach -t piserviceui`.

**Capacity:** with 512 MB RAM, budget for the Docker daemon + host container + each
`discord.py` process (~40–70 MB). Realistically ~3–5 light bots. Keep an eye on it with
`docker stats`.

---

## Bare-metal fallback (no Docker)

If Docker overhead is too much on the Zero, run the same app directly. Build the frontend
once (`cd web && npm install && npm run build`), install host deps
(`pip install -r requirements.txt`), then keep it alive with systemd:

```ini
# /etc/systemd/system/piserviceui.service
[Unit]
Description=PiServiceUi
After=network-online.target

[Service]
WorkingDirectory=/home/pi/piserviceui
EnvironmentFile=/home/pi/piserviceui/.env
ExecStart=/home/pi/piserviceui/.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8080
Restart=on-failure
User=pi

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable --now piserviceui
```

Raspberry Pi OS ships with piwheels preconfigured, so service `pip install`s use prebuilt
ARM wheels automatically.

---

## Notes & limits

- Services persist across host restarts: anything running when the host stopped (plus
  `autostart: true` services) is resumed on boot.
- Auto-restart honours each service's `restart` policy, with a guard of 5 restarts / 60 s
  to avoid crash loops.
- After upgrading the Python base image, clear `data/venvs/` so venvs are rebuilt against
  the new interpreter.
- Set `COOKIE_SECURE=true` only when serving over HTTPS (e.g. behind a reverse proxy).
