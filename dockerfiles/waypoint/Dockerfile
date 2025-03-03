FROM python:3.12-slim

WORKDIR /waypoint

COPY waypoint/poetry.lock /waypoint
COPY waypoint/pyproject.toml /waypoint

ARG POETRY_VERSION=2.1.1
RUN pip install --no-cache-dir poetry==${POETRY_VERSION}
# Set Poetry's cache and virtualenvs path to a writable directory
ENV POETRY_CACHE_DIR=/tmp/.cache/pypoetry
RUN poetry config cache-dir "$POETRY_CACHE_DIR" && \
  poetry config virtualenvs.path "$POETRY_CACHE_DIR/virtualenvs" && \
  poetry install

COPY waypoint /waypoint
COPY shared /shared

EXPOSE 3011

USER nobody

CMD ["poetry", "run", "uvicorn", "waypoint.main:app", "--reload", "--host", "0.0.0.0", "--port", "3011"]
