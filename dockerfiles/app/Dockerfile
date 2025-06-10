FROM python:3.12.10-slim

WORKDIR /app

COPY poetry.lock /app
COPY pyproject.toml /app

COPY dockerfiles/poetry-requirements.txt /app
RUN pip install --no-cache-dir -r poetry-requirements.txt

# Set Poetry's cache and virtualenvs path to a writable directory
ENV POETRY_CACHE_DIR=/poetry
RUN poetry config cache-dir "$POETRY_CACHE_DIR" && \
  poetry config virtualenvs.path "$POETRY_CACHE_DIR/virtualenvs" && \
  poetry install --only main,app

COPY app /app
COPY shared /shared

EXPOSE 8000

USER nobody

ENV PYTHONPATH=/

CMD ["poetry", "run", "uvicorn", "app.main:app", "--reload", "--host", "0.0.0.0", "--port", "8000"]
