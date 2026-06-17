# syntax=docker/dockerfile:1

# --- Stage 1: build the React bundle on the *build* platform (fast) ---------
FROM --platform=$BUILDPLATFORM node:20-alpine AS web
WORKDIR /web
COPY web/package.json web/package-lock.json* ./
RUN npm install
COPY web/ ./
RUN npm run build            # -> /web/dist

# --- Stage 2: runtime on the Pi (ARMv6) -------------------------------------
# Pin the ARMv6 variant explicitly; the multi-arch `python` manifest often
# omits linux/arm/v6, which is what the Pi Zero W v1.1 needs.
FROM arm32v6/python:3.11-slim-bullseye AS runtime

# Prefer piwheels for prebuilt ARM wheels (both for host deps and service venvs).
RUN printf '[global]\nextra-index-url=https://www.piwheels.org/simple\n' > /etc/pip.conf

# Uncomment if a bot needs to compile C/Rust extensions with no wheel available:
# RUN apt-get update && apt-get install -y --no-install-recommends \
#       build-essential libffi-dev && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app
COPY --from=web /web/dist ./web/dist

# services/ and data/ are bind-mounted at runtime (see docker-compose.yml).
EXPOSE 8080
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
