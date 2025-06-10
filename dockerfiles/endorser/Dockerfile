FROM python:3.12.10-slim

WORKDIR /endorser

COPY poetry.lock /endorser
COPY pyproject.toml /endorser

COPY dockerfiles/poetry-requirements.txt /endorser
RUN pip install --no-cache-dir -r poetry-requirements.txt

# Set Poetry's cache and virtualenvs path to a writable directory
ENV POETRY_CACHE_DIR=/poetry
RUN poetry config cache-dir "$POETRY_CACHE_DIR" && \
  poetry config virtualenvs.path "$POETRY_CACHE_DIR/virtualenvs" && \
  poetry install --only main,endorser

COPY endorser /endorser
COPY shared /shared

EXPOSE 3009

USER nobody

ENV PYTHONPATH=/

CMD ["poetry", "run", "uvicorn", "endorser.main:app", "--reload", "--host", "0.0.0.0", "--port", "3009"]
