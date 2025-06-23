FROM python:3.12.11-slim

WORKDIR /revocation_service

COPY poetry.lock /revocation_service
COPY pyproject.toml /revocation_service

COPY dockerfiles/poetry-requirements.txt /revocation_service
RUN pip install --no-cache-dir -r poetry-requirements.txt --require-hashes

# Set Poetry's cache and virtualenvs path to a writable directory
ENV POETRY_CACHE_DIR=/poetry
RUN poetry config cache-dir "$POETRY_CACHE_DIR" && \
  poetry config virtualenvs.path "$POETRY_CACHE_DIR/virtualenvs" && \
  poetry install --only main,revocation-service

COPY revocation_service /revocation_service
COPY shared /shared

EXPOSE 3012

USER nobody

ENV PYTHONPATH=/

CMD ["poetry", "run", "uvicorn", "revocation_service.main:app", "--reload", "--host", "0.0.0.0", "--port", "3012"]
