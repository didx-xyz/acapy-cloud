FROM python:3.13-slim@sha256:21e39cf1815802d4c6f89a0d3a166cc67ce58f95b6d1639e68a394c99310d2e5

WORKDIR /waypoint

COPY poetry.lock /waypoint
COPY pyproject.toml /waypoint

ARG POETRY_VERSION=2.1.1
RUN pip install --no-cache-dir poetry==${POETRY_VERSION}
# Set Poetry's cache and virtualenvs path to a writable directory
ENV POETRY_CACHE_DIR=/tmp/.cache/pypoetry
RUN poetry config cache-dir "$POETRY_CACHE_DIR" && \
  poetry config virtualenvs.path "$POETRY_CACHE_DIR/virtualenvs" && \
  poetry install --only main,waypoint

COPY waypoint /waypoint
COPY shared /shared

EXPOSE 3011

USER nobody

CMD ["poetry", "run", "uvicorn", "waypoint.main:app", "--reload", "--host", "0.0.0.0", "--port", "3011"]
