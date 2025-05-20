FROM ghcr.io/didx-xyz/acapy-agent:py3.12-debug-connections@sha256:74f82c137261e088e3af28518522d5ec54c284b32d96ce3bfe7e6e9ced24bbcd

USER root

# Install Google Protobuf and Plugins
ARG PROTOBUF_VERSION=5.29.3
RUN pip install --no-cache-dir protobuf==${PROTOBUF_VERSION} \
  acapy-wallet-groups-plugin==1.3.0.post20250506 \
  git+https://github.com/didx-xyz/aries-acapy-plugins@b54dddc49#subdirectory=nats_events \
  git+https://github.com/didx-xyz/aries-acapy-plugins@b54dddc49#subdirectory=cheqd

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
