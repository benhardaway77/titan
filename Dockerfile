# Titan (paper-first) Docker image
# Build context: this titan/ folder

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# System deps (keep minimal)
RUN apt-get update \
  && apt-get install -y --no-install-recommends ca-certificates curl \
  && rm -rf /var/lib/apt/lists/*

# Install python deps
COPY pyproject.toml /app/pyproject.toml
COPY src/ /app/src/

RUN pip install --no-cache-dir -U pip \
  && pip install --no-cache-dir -e .

# Optional: runtime state dir mounted from Unraid
RUN mkdir -p /app/state

# Default to paper mode
ENV TITAN_ENV=paper \
    TITAN_ENABLE_LIVE=false

# NOTE: Titan currently is a scaffold (prints placeholder). When Titan grows,
# this container will run the long-lived worker.
ENTRYPOINT ["titan"]
CMD ["run","--env","paper"]
