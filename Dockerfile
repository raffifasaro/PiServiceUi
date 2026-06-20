# syntax=docker/dockerfile:1

# --- Stage 1: build the React bundle on the *build* platform (fast) ---------
FROM --platform=$BUILDPLATFORM node:20-alpine AS web
WORKDIR /web
COPY web/package.json web/package-lock.json* ./
RUN npm install
COPY web/ ./
RUN npm run build            # -> /web/dist

# --- Stage 2: runtime on the Pi (ARMv6) -------------------------------------
# The official `python` manifest omits linux/arm/v6, and `arm32v6/python` only
# ships Alpine (musl) tags -- which break piwheels' glibc wheels. Balena's
# rpi-python is Debian Bullseye on glibc for the Pi Zero/1 (ARMv6), so piwheels
# prebuilt wheels work.
FROM balenalib/rpi-python:3.11.2-bullseye-run AS runtime

# Prefer piwheels for prebuilt ARM wheels (both for host deps and service venvs).
# prefer-binary: pick the newest version that has a wheel rather than a newer
# sdist (avoids compiling Rust/C on the Pi, e.g. pydantic-core).
RUN printf '[global]\nextra-index-url=https://www.piwheels.org/simple\nprefer-binary=true\n' > /etc/pip.conf

# Uncomment if a bot needs to compile C/Rust extensions with no wheel available:
# RUN apt-get update && apt-get install -y --no-install-recommends \
#       build-essential libffi-dev && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
# Balena's base ships pip 23.0, which rejects piwheels' PEP 658 metadata when the
# dist name differs by hyphen/underscore (e.g. pydantic_core), forcing a source
# build (Rust). A newer pip normalizes the name and uses the prebuilt wheel.
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -r requirements.txt

COPY app/ ./app
COPY --from=web /web/dist ./web/dist

# services/ and data/ are bind-mounted at runtime (see docker-compose.yml).
EXPOSE 8080
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
