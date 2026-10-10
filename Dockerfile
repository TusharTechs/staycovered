# StayCovered: single container (FastAPI API + built React app)
FROM node:22-slim AS web
WORKDIR /app/web
RUN corepack enable
COPY web/package.json web/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY web/ ./
RUN pnpm build

FROM python:3.12-slim
WORKDIR /app
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project
COPY staycovered/ staycovered/
COPY rules/ rules/
COPY sources/ sources/
COPY bench/ bench/
COPY demo/ demo/
COPY data/ data/
COPY --from=web /app/web/dist web/dist
RUN uv sync --frozen --no-dev
ENV PORT=8000
EXPOSE 8000
CMD ["sh", "-c", "uv run --no-dev uvicorn staycovered.api:app --host 0.0.0.0 --port ${PORT}"]
