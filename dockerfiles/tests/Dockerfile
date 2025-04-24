FROM python:3.13-slim@sha256:21e39cf1815802d4c6f89a0d3a166cc67ce58f95b6d1639e68a394c99310d2e5

# Copy the pyproject.toml and lock file
COPY pyproject.toml cloudapi-tests/
COPY poetry.lock cloudapi-tests/

WORKDIR /cloudapi-tests

# Install all dependencies
ARG POETRY_VERSION=2.1.1
RUN pip install --no-cache-dir poetry==${POETRY_VERSION}

ENV POETRY_VIRTUALENVS_CREATE=false
RUN poetry install

COPY . .

# docker compose overwrites this
CMD ["pytest", "--junitxml=test_output.xml"]
