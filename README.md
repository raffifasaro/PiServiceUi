# PiServiceUi

![License](https://img.shields.io/badge/license-MIT-blue)
![Python](https://img.shields.io/badge/python-3.10%2B-green)
![Backend](https://img.shields.io/badge/backend-FastAPI-009688)
![Frontend](https://img.shields.io/badge/frontend-React%20%2B%20Vite-61dafb)

A password-protected control panel for running small services on a Raspberry Pi Zero W. I built it to keep a couple of Python Discord bots alive on a Pi without SSHing in every time one fell over. Each service runs as a managed subprocess, and a web UI lets you start, stop, and restart them while watching CPU, memory, and uptime.

## What you get

- A sidebar with live host stats: CPU, memory, disk, temperature, load, and uptime.
- One card per service showing its status, CPU/RAM, uptime, controls, and a log tail.
- Drop-in services: add a folder with a `service.yaml` under `services/`, hit **Rescan**, and it shows up. No restart needed.

The host runs in Docker. Each service gets its own virtualenv under `data/venvs/<name>`, so one bot's dependencies can't break another's.

## How it fits together

```
Browser ──LAN──> FastAPI (uvicorn, in Docker) ──> serves the built React app
                      │  REST + SSE (cookie auth)
                      ▼
                ServiceManager ──spawns──> bot subprocess (own venv) …
                      │  psutil: per-PID + host metrics
```

| Layer | What it uses |
|-------|--------------|
| Backend | FastAPI, uvicorn, `psutil`, `passlib` (pbkdf2), `itsdangerous` sessions |
| Frontend | React, Vite, TypeScript (built to static files, served by the backend) |
| Services | discovered from `services/*/service.yaml`, each in its own venv |

## Adding a service

Lay out a folder like this:

```
services/
  my-bot/
    service.yaml
    bot.py
    requirements.txt   # optional
    .env               # optional (DISCORD_TOKEN=...)
```

Then write its `service.yaml`:

```yaml
name: my-bot
description: "My Discord bot"
entrypoint: bot.py          # a .py file, or a module path like "package.module"
requirements: requirements.txt
env_file: .env
autostart: false            # start when the host boots
restart: on-failure         # never | on-failure | always
```

`services/sample-bot/` is a working example that needs no Discord token, so it's safe to start and stop while you poke around. Once the folder is in place, click **Rescan** in the UI.

## Setting a password

Login is gated by a single password, stored as a hash. Copy the example env file and fill in two values:

```bash
cp .env.example .env
python scripts/hash-password.py                           # paste into UI_PASSWORD_HASH
python -c "import secrets; print(secrets.token_hex(32))"  # paste into SESSION_SECRET
```

## Running locally

You'll want two terminals. Backend first:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1        # Windows; use `source .venv/bin/activate` elsewhere
pip install -r requirements.txt
copy .env.example .env              # then fill UI_PASSWORD_HASH + SESSION_SECRET
python -m uvicorn app.main:app --reload --port 8080
```

Then the frontend. Vite proxies `/api` to the backend, so it all looks like one origin:

```powershell
cd web
npm install
npm run dev
```

Open http://localhost:5173, log in, and try starting `sample-bot`. You should see its CPU/RAM and uptime tick up in the card and the host meters move in the sidebar. Open **Logs** to tail its output.

A couple of things behave differently off a Pi: on Windows and macOS the host CPU temperature shows `—` (there's no `/sys` thermal zone to read), and stopping a process uses `terminate()` rather than POSIX signals. Both are expected.

## Deploying on the Pi (Docker + tmux)

The Pi Zero W is ARMv6, which Docker won't build for natively on a modern x86 machine. The trick is to build the image on your dev machine with buildx, targeting the Pi's platform, then run it on the Pi. React gets compiled inside the image's build stage on your machine, so nothing heavy has to run on the Zero.

On your dev machine:

```bash
# one-time: enable buildx emulation
docker buildx create --use

# build for the Pi, then load (or push to a registry the Pi can reach)
docker buildx build --platform linux/arm/v6 -t piserviceui:latest --load .
```

On the Pi:

```bash
git clone <your-repo> piserviceui && cd piserviceui
cp .env.example .env        # set UI_PASSWORD_HASH + SESSION_SECRET
# drop your bot folders into services/
bash scripts/start-tmux.sh  # docker compose up -d, plus an attachable `logs -f` in tmux
```

Now browse to `http://<pi-ip>:8080`. Detach from tmux with `Ctrl-b d`; reattach later with `tmux attach -t piserviceui`.

On capacity: with 512 MB of RAM, you're budgeting for the Docker daemon, the host container, and each `discord.py` process (roughly 40–70 MB apiece). In practice that's about 3 to 5 light bots. Watch it with `docker stats`.

## Bare-metal fallback (no Docker)

If Docker is too much overhead on the Zero, you can run the same app directly. Build the frontend once with `cd web && npm install && npm run build`, install the host deps with `pip install -r requirements.txt`, and let systemd keep it alive:

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

Raspberry Pi OS comes with piwheels configured, so a service's `pip install` pulls prebuilt ARM wheels instead of compiling from source.

## API

Everything the UI does goes through a small REST + SSE surface (all cookie-authenticated):

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/api/login`, `/api/logout` | session in/out |
| `GET` | `/api/auth/check` | is the session valid |
| `GET` | `/api/services` | list services and status |
| `POST` | `/api/services/rescan` | pick up new/changed `service.yaml` files |
| `POST` | `/api/services/{name}/start\|stop\|restart` | lifecycle controls |
| `GET` | `/api/services/{name}/logs` | recent log lines |
| `GET` | `/api/metrics/host` | host CPU/mem/disk/temp/load/uptime |
| `GET` | `/api/stream` | SSE feed of status + metrics |

## Good to know

- State survives restarts. Anything running when the host stopped, plus any `autostart: true` services, comes back up on boot.
- Auto-restart follows each service's `restart` policy, capped at 5 restarts in 60 seconds so a crash loop can't run away.
- After bumping the Python base image, delete `data/venvs/` so the per-service venvs get rebuilt against the new interpreter.
- Only set `COOKIE_SECURE=true` when you're actually serving over HTTPS (for example behind a reverse proxy), otherwise the login cookie won't be sent.

## License

MIT. See [LICENSE](LICENSE).
