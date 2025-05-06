FROM ghcr.io/didx-xyz/acapy-agent:py3.12-1.3.0-20250505@sha256:941c04facd7219904cec6eb3b0f3f6012528bad6fae7a91c0b73bc869a3fba87

USER root

# Install Google Protobuf and Plugins
ARG PROTOBUF_VERSION=5.29.3
RUN pip install --no-cache-dir protobuf==${PROTOBUF_VERSION} \
  acapy-wallet-groups-plugin==1.3.0.post20250506 \
  git+https://github.com/didx-xyz/aries-acapy-plugins@1.3.0-20250505#subdirectory=nats_events

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
