FROM ghcr.io/didx-xyz/acapy-agent:py3.12-1.3.1-20250702@sha256:6bff9f8c248a385f36e539f948fe43d005996451612d6da904b0d0299451d906

USER root

# Copy agent dependency definitions
COPY dockerfiles/poetry-requirements.txt /plugin-deps/poetry-requirements.txt
COPY dockerfiles/agents/pyproject.toml /plugin-deps/pyproject.toml
COPY dockerfiles/agents/poetry.lock /plugin-deps/poetry.lock
WORKDIR /plugin-deps

# Install poetry with pinned hashes
RUN pip install --no-cache-dir -r poetry-requirements.txt --require-hashes

# Install dependencies
ENV POETRY_VIRTUALENVS_CREATE=false
RUN poetry install

WORKDIR /
COPY scripts/startup.sh startup.sh
RUN chmod +x ./startup.sh

USER aries

ENTRYPOINT [ "./startup.sh" ]
CMD [ "--wallet-type", "askar-anoncreds", \
  ## Setting for Governance Agent and Multitenant Agent
  "--plugin", "nats_events.v1_0.nats_queue.events", \
  ## Additional settings for Multitenant Agent only
  #   "--auto-promote-author-did", \
  #   "--plugin", "acapy_wallet_groups_plugin", \
  "--plugin-config-value", "nats_queue.connection.connection_url=\"nats://nats-1:4222\""]
