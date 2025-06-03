FROM python:3.12.10-slim

WORKDIR /tails

COPY poetry.lock /tails
COPY pyproject.toml /tails

ARG POETRY_VERSION=2.1.3
RUN pip install --no-cache-dir poetry==${POETRY_VERSION}
# Set Poetry's cache and virtualenvs path to a writable directory
ENV POETRY_CACHE_DIR=/poetry
RUN poetry config cache-dir "$POETRY_CACHE_DIR" && \
  poetry config virtualenvs.path "$POETRY_CACHE_DIR/virtualenvs" && \
  poetry install --only main,tails

COPY tails /tails
COPY shared /shared

EXPOSE 6543

USER nobody

ENV PYTHONPATH=/

CMD ["poetry", "run", "uvicorn", "tails.main:app", "--reload", "--host", "0.0.0.0", "--port", "6543"]
