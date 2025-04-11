FROM python:3.12-slim

WORKDIR /trustregistry

COPY poetry.lock /trustregistry
COPY pyproject.toml /trustregistry

ARG POETRY_VERSION=2.1.1
RUN pip install --no-cache-dir poetry==${POETRY_VERSION}
# Set Poetry's cache and virtualenvs path to a writable directory
ENV POETRY_CACHE_DIR=/tmp/.cache/pypoetry
RUN poetry config cache-dir "$POETRY_CACHE_DIR" && \
  poetry config virtualenvs.path "$POETRY_CACHE_DIR/virtualenvs" && \
  poetry install --only trust-registry

COPY trustregistry /trustregistry
COPY shared /shared

EXPOSE 8001

USER nobody

CMD ["poetry", "run", "uvicorn", "trustregistry.main:app", "--reload", "--host", "0.0.0.0", "--port", "8001"]
