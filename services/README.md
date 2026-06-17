# Drop your services here

Each service is a subfolder containing a `service.yaml` manifest plus your code.
The host auto-discovers them on startup and when you click **Rescan** in the UI.

```
services/
  my-bot/
    service.yaml        # required
    bot.py              # your entrypoint
    requirements.txt    # optional — installed into an isolated venv
    .env                # optional — loaded into the process environment
```

### `service.yaml`

```yaml
name: my-bot                 # unique; defaults to the folder name
description: "What it does"
entrypoint: bot.py           # a .py file, or a module path like "package.module"
requirements: requirements.txt   # optional
env_file: .env               # optional (put DISCORD_TOKEN=... here)
autostart: false             # start automatically when the host boots
restart: on-failure          # never | on-failure | always
```

Each service runs in its own virtualenv under `data/venvs/<name>`, so their
dependencies never collide. See `sample-bot/` for a working example.
