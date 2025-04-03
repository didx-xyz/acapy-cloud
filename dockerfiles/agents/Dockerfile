FROM ghcr.io/didx-xyz/acapy-agent:py3.12-test-revocation-logging

USER root

RUN echo "Installing plugins"

# Install Google Protobuf and Plugins
ARG PROTOBUF_VERSION=5.29.3
RUN pip install --no-cache-dir protobuf==${PROTOBUF_VERSION} \
  acapy-wallet-groups-plugin==1.2.1.post20250327 \
  # git+https://github.com/didx-xyz/acapy-wallet-groups-plugin@release-1.2.1-20250327 \
  git+https://github.com/didx-xyz/aries-acapy-plugins@1.2.1-20250327#subdirectory=nats_events

COPY scripts/startup.sh startup.sh
RUN chmod +x ./startup.sh

USER aries

ENTRYPOINT [ "./startup.sh" ]
CMD [ "--wallet-type", "askar", \
  ## Setting for Governance Agent and Multitenant Agent
  "--plugin", "nats_events.v1_0.nats_queue.events", \
  ## Additional settings for Multitenant Agent only
  #   "--auto-promote-author-did", \
  #   "--plugin", "acapy_wallet_groups_plugin", \
  "--plugin-config-value", "nats_queue.connection.connection_url=\"nats://nats-1:4222\""]
