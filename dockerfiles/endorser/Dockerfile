FROM python:3.13.3-slim

WORKDIR /endorser

COPY poetry.lock /endorser
COPY pyproject.toml /endorser

ARG POETRY_VERSION=2.1.1
RUN pip install --no-cache-dir poetry==${POETRY_VERSION}
# Set Poetry's cache and virtualenvs path to a writable directory
ENV POETRY_CACHE_DIR=/tmp/.cache/pypoetry
RUN poetry config cache-dir "$POETRY_CACHE_DIR" && \
  poetry config virtualenvs.path "$POETRY_CACHE_DIR/virtualenvs" && \
  poetry install --only main,endorser

COPY endorser /endorser
COPY shared /shared

EXPOSE 3009

USER nobody

ENV PYTHONPATH=/

CMD ["poetry", "run", "uvicorn", "endorser.main:app", "--reload", "--host", "0.0.0.0", "--port", "3009"]
