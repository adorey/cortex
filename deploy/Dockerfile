# cortex-runtime image. Build context = the repo root (it needs core/, runtime/ and mcp/):
#   docker build -f deploy/Dockerfile -t cortex-runtime .
#
# Bundles: the Python runtime + API, the cortex-jsm MCP server (on PATH as `cortex-jsm-mcp`),
# and the Claude Code CLI (Node) so the `claude-cli` backend works in-container. For an
# `anthropic-api` or `demo` backend you can drop the Node layer (smaller image).
FROM python:3.12-slim

# Node + the Claude Code CLI (claude-cli backend) + git (real working tree).
RUN apt-get update && apt-get install -y --no-install-recommends \
        nodejs npm git ca-certificates \
    && npm install -g @anthropic-ai/claude-code \
    && npm cache clean --force \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY core/ /app/core/
COPY runtime/ /app/runtime/
COPY mcp/ /app/mcp/
# cortex-core in the same command as the runtime that depends on it, so pip resolves it from
# /app/core and never looks for it on an index (ADR-007).
RUN pip install --no-cache-dir "/app/core" "/app/runtime/.[serve,postgres]" "/app/mcp"

RUN useradd -m -u 10001 cortex && chown -R cortex /app
USER cortex

ENV CORTEX_HOST=0.0.0.0 \
    CORTEX_PORT=8000 \
    DISABLE_TELEMETRY=1 \
    DO_NOT_TRACK=1

EXPOSE 8000
CMD ["python", "-m", "cortex_runtime"]
