FROM python:3.12-slim@sha256:85824326bc4ae27a1abb5bc0dd9e08847aa5fe73d8afb593b1b45b7cb4180f57

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
