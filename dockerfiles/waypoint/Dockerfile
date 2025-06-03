FROM python:3.12.10-slim

WORKDIR /waypoint

COPY poetry.lock /waypoint
COPY pyproject.toml /waypoint

ARG POETRY_VERSION=2.1.3
RUN pip install --no-cache-dir poetry==${POETRY_VERSION}
# Set Poetry's cache and virtualenvs path to a writable directory
ENV POETRY_CACHE_DIR=/poetry
RUN poetry config cache-dir "$POETRY_CACHE_DIR" && \
  poetry config virtualenvs.path "$POETRY_CACHE_DIR/virtualenvs" && \
  poetry install --only main,waypoint

COPY waypoint /waypoint
COPY shared /shared

EXPOSE 3011

USER nobody

ENV PYTHONPATH=/

CMD ["poetry", "run", "uvicorn", "waypoint.main:app", "--reload", "--host", "0.0.0.0", "--port", "3011"]
