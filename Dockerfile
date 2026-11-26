FROM python:3.11-slim-bookworm

RUN pip install --no-cache-dir uv==0.12.5

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TURNWISE_HTTP_HOST=0.0.0.0 \
    TURNWISE_LOG_JSON=true

COPY pyproject.toml uv.lock ./
COPY server ./server
COPY pipeline ./pipeline
COPY models ./models
COPY dialogue ./dialogue
COPY nlp ./nlp
COPY tools ./tools
COPY evals ./evals
COPY training ./training
COPY data ./data
COPY client ./client

RUN uv sync --frozen --no-dev --extra tts --extra asr

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

CMD ["python", "-m", "server"]
