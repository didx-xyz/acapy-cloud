FROM ghcr.io/didx-xyz/acapy-agent:py3.12-1.3.0rc1-20250417@sha256:cf02cef079bccd66a14a959a1c17e3f0e6e8cb3c859c90d01e5a5312af0b60b7

USER root

RUN echo "Installing plugins"

# Install Google Protobuf and Plugins
ARG PROTOBUF_VERSION=5.29.3
RUN pip install --no-cache-dir protobuf==${PROTOBUF_VERSION} \
  acapy-wallet-groups-plugin==1.3.0rc1.post20250417 \
  # git+https://github.com/didx-xyz/acapy-wallet-groups-plugin@release-1.3.0rc1-20250417 \
  git+https://github.com/didx-xyz/aries-acapy-plugins@1.3.0rc1-20250417#subdirectory=nats_events

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
