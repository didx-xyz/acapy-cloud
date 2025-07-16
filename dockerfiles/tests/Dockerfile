FROM python:3.12.11-slim

# Copy the pyproject.toml and lock file
COPY pyproject.toml cloudapi-tests/
COPY poetry.lock cloudapi-tests/

WORKDIR /cloudapi-tests

COPY dockerfiles/poetry-requirements.txt /cloudapi-tests
RUN pip install --no-cache-dir -r poetry-requirements.txt --require-hashes

# Install all dependencies
ENV POETRY_VIRTUALENVS_CREATE=false
RUN poetry install

COPY ./app ./app
COPY ./shared ./shared
COPY ./tails ./tails
COPY ./trustregistry ./trustregistry
COPY ./waypoint ./waypoint

# docker compose overwrites this
CMD ["pytest", "--junitxml=test_output.xml"]
