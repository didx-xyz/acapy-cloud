FROM python:3.12.10-slim

WORKDIR /app

COPY poetry.lock /app
COPY pyproject.toml /app

ARG POETRY_VERSION=2.1.1
RUN pip install --no-cache-dir poetry==${POETRY_VERSION}
# Set Poetry's cache and virtualenvs path to a writable directory
ENV POETRY_CACHE_DIR=/tmp/.cache/pypoetry
RUN poetry config cache-dir "$POETRY_CACHE_DIR" && \
  poetry config virtualenvs.path "$POETRY_CACHE_DIR/virtualenvs" && \
  poetry install --only main,app

COPY app /app
COPY shared /shared

EXPOSE 8000

USER nobody

ENV PYTHONPATH=/

CMD ["poetry", "run", "uvicorn", "app.main:app", "--reload", "--host", "0.0.0.0", "--port", "8000"]
