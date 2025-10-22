FROM python:3.12.12-slim

WORKDIR /waypoint

COPY poetry.lock /waypoint
COPY pyproject.toml /waypoint

COPY dockerfiles/poetry-requirements.txt /waypoint
RUN pip install --no-cache-dir -r poetry-requirements.txt --require-hashes

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
