# PulseNet API + dashboard, as deployed on Render (see render.yaml). Keys come from the host's environment.
FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.8.0 /uv /uvx /usr/local/bin/
ENV UV_LINK_MODE=copy PYTHONUNBUFFERED=1
WORKDIR /app

COPY . .
# build the data, download the standards and the embedding model, and install the scripts' environments once
RUN uv sync --no-dev \
 && uv run python pulsenet/fetch_standards.py \
 && uv run python pulsenet/prepare_data.py \
 && uv run python -c "import sys; sys.path.insert(0, 'pulsenet'); import knowledge; knowledge.search('fiber cut')" \
 && uv run pulsenet/api.py --help > /dev/null \
 && uv run pulsenet/network_mcp.py --help > /dev/null

CMD ["bash", "deploy/start.sh"]
