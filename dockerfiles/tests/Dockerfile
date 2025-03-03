FROM python:3.12-slim

WORKDIR /cloudapi-tests

# Copy the pyproject.toml for each submodule
COPY app/pyproject.toml app/
COPY endorser/pyproject.toml endorser/
COPY trustregistry/pyproject.toml trustregistry/
COPY waypoint/pyproject.toml waypoint/

# Copy the lock files for each submodule
COPY app/poetry.lock app/
COPY endorser/poetry.lock endorser/
COPY trustregistry/poetry.lock trustregistry/
COPY waypoint/poetry.lock waypoint/

# Install all dependencies
ARG POETRY_VERSION=2.1.1
RUN pip install --no-cache-dir poetry==${POETRY_VERSION}

ENV POETRY_VIRTUALENVS_CREATE=false
ARG MODULES="app endorser trustregistry waypoint"
RUN for module in ${MODULES}; do \
  cd "/cloudapi-tests/$module" && poetry install; \
  done

COPY . .

# docker compose overwrites this
CMD ["pytest", "--junitxml=test_output.xml"]
