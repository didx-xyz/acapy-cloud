FROM ghcr.io/didx-xyz/acapy-agent:py3.12-1.3.0-20250609@sha256:04b1b617c730fbefe4a994ae80dd953448f852c69a3e98bc8311c950bfc961f4

USER root

# Copy plugin dependencies
COPY dockerfiles/agents/pyproject.toml /plugin-deps/pyproject.toml
COPY dockerfiles/agents/poetry.lock /plugin-deps/poetry.lock
WORKDIR /plugin-deps

# Install dependencies (ACA-Py has poetry pre-installed)
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
