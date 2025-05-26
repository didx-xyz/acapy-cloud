FROM ghcr.io/didx-xyz/acapy-agent:py3.12-1.3.0-20250526@sha256:6d02573554820d3114ea3a74a863386cd9f536583bc77188623d3d10fab38d8a

USER root

# Install Google Protobuf and Plugins
ARG PROTOBUF_VERSION=5.29.3
RUN pip install --no-cache-dir protobuf==${PROTOBUF_VERSION} \
  acapy-wallet-groups-plugin==1.3.0.post20250506 \
  git+https://github.com/didx-xyz/aries-acapy-plugins@5814bf13#subdirectory=nats_events \
  git+https://github.com/didx-xyz/aries-acapy-plugins@5814bf13#subdirectory=cheqd

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
