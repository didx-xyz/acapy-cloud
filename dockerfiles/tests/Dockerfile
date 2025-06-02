FROM python:3.12.10-slim

# Copy the pyproject.toml and lock file
COPY pyproject.toml cloudapi-tests/
COPY poetry.lock cloudapi-tests/

WORKDIR /cloudapi-tests

# Install all dependencies
ARG POETRY_VERSION=2.1.3
RUN pip install --no-cache-dir poetry==${POETRY_VERSION}

ENV POETRY_VIRTUALENVS_CREATE=false
RUN poetry install

COPY . .

# docker compose overwrites this
CMD ["pytest", "--junitxml=test_output.xml"]
