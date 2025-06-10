FROM python:3.12.11-slim

WORKDIR /trustregistry

COPY poetry.lock /trustregistry
COPY pyproject.toml /trustregistry

COPY dockerfiles/poetry-requirements.txt /trustregistry
RUN pip install --no-cache-dir -r poetry-requirements.txt

# Set Poetry's cache and virtualenvs path to a writable directory
ENV POETRY_CACHE_DIR=/poetry
RUN poetry config cache-dir "$POETRY_CACHE_DIR" && \
  poetry config virtualenvs.path "$POETRY_CACHE_DIR/virtualenvs" && \
  poetry install --only main,trust-registry

COPY trustregistry /trustregistry
COPY shared /shared

EXPOSE 8001

USER nobody

ENV PYTHONPATH=/

CMD ["poetry", "run", "uvicorn", "trustregistry.main:app", "--reload", "--host", "0.0.0.0", "--port", "8001"]
