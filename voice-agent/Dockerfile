# Villa voice agent worker (LiveKit Agents). Dials out only: LiveKit Cloud, OpenRouter,
# ElevenLabs, the VillaOps MCP servers and the backend — no ports to publish.
FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv

COPY --from=ghcr.io/astral-sh/uv:0.6.10 /uv /usr/local/bin/uv

WORKDIR /app

# Dependencies first (cached unless the lockfile changes)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY agent.py ./
COPY villa ./villa

RUN groupadd --gid 1000 villa && useradd --uid 1000 --gid villa --create-home villa && chown -R villa:villa /app
USER villa

# "start" = production mode (no dev defaults); one call process kept warm
CMD ["/app/.venv/bin/python", "agent.py", "start"]
