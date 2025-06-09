FROM ghcr.io/didx-xyz/acapy-agent:py3.12-test-1.3.0-20250609@sha256:95d4df7e45753da7d2db9d755268cb6863781eb1ef42f1ad9b6b2203c42d0c0b

USER root

# Install Google Protobuf and Plugins
ARG PROTOBUF_VERSION=5.29.3
RUN echo "Installing Plugins"
RUN pip install --no-cache-dir protobuf==${PROTOBUF_VERSION} \
  acapy-wallet-groups-plugin==1.3.0.post20250526 \
  git+https://github.com/didx-xyz/aries-acapy-plugins@1.3.0-20250526#subdirectory=nats_events \
  git+https://github.com/didx-xyz/aries-acapy-plugins@70b44aa6eff#subdirectory=cheqd

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
