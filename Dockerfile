# StayCovered: single container (FastAPI API + built React app). Works on Hugging Face Spaces (port 7860) or any Docker host.
FROM node:22-slim AS web
WORKDIR /app/web
RUN npm install -g pnpm@12.10.1
COPY web/package.json web/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY web/ ./
RUN pnpm build

FROM python:3.12-slim
RUN pip install --no-cache-dir uv && useradd -m -u 1000 user
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project
COPY staycovered/ staycovered/
COPY rules/ rules/
COPY sources/ sources/
COPY bench/ bench/
COPY demo/ demo/
COPY data/ data/
COPY --from=web /app/web/dist web/dist
RUN uv sync --frozen --no-dev && mkdir -p data/runtime && chown -R user:user /app
USER user
ENV PORT=7860 HOME=/home/user
EXPOSE 7860
CMD ["sh", "-c", ".venv/bin/uvicorn staycovered.api:app --host 0.0.0.0 --port ${PORT}"]
