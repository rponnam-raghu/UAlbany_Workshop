FROM python:3.12-slim-bookworm AS base
COPY --from=ghcr.io/astral-sh/uv:0.9.8 /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 STREAMLIT_BROWSER_GATHER_USAGE_STATS=false
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --locked --no-dev --no-install-project
COPY src ./src
COPY streamlit_app.py ./
COPY .streamlit ./.streamlit
COPY data ./data
COPY migrations ./migrations
COPY README.md ./README.md
RUN --mount=type=cache,target=/root/.cache/uv uv sync --locked --no-dev
RUN useradd --create-home --uid 10001 advisor && mkdir -p /app/runtime && chown advisor /app/runtime
EXPOSE 8501
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=5 \
  CMD ["/app/.venv/bin/python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8501/_stcore/health', timeout=4)"]
USER advisor
CMD ["uv", "run", "--no-sync", "streamlit", "run", "streamlit_app.py", "--server.address=0.0.0.0"]

FROM base AS development
ENV PYTEST_ADDOPTS="-o cache_dir=/tmp/advisor-pytest-cache" \
    RUFF_CACHE_DIR=/tmp/advisor-ruff-cache MYPY_CACHE_DIR=/tmp/advisor-mypy-cache
USER root
RUN --mount=type=cache,target=/root/.cache/uv uv sync --locked
COPY tests ./tests
USER advisor
