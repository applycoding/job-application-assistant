FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:0.13.5 /uv /bin/uv

WORKDIR /app

COPY pyproject.toml uv.lock README.md ./
COPY src/ ./src/
RUN uv sync --locked --no-dev --extra llm

COPY samples/ ./samples/

RUN useradd --uid 10001 --create-home app && mkdir -p /data && chown 10001:10001 /data

ENV JAA_HOST=0.0.0.0
ENV JAA_DB_PATH=/data/jaa.sqlite3
ENV PATH="/app/.venv/bin:$PATH"

VOLUME /data
EXPOSE 8000

USER 10001

HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request,sys;sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz',timeout=2).status==200 else 1)"

CMD ["jaa", "serve"]
