ARG BBS_SUFFIX="-bbs"
FROM ghcr.io/didx-xyz/acapy-agent${BBS_SUFFIX}:py3.12-1.2.1-20250227

USER root

# Install Google Protobuf and Plugins
ARG PROTOBUF_VERSION=5.29.3
RUN pip install --no-cache-dir protobuf==${PROTOBUF_VERSION} \
  git+https://github.com/didx-xyz/acapy-wallet-groups-plugin@release-1.2.1-20250227 \
  git+https://github.com/didx-xyz/aries-acapy-plugins@9878ac5e95851ebb05e6292c133d8e97cf3e642e#subdirectory=nats_events

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
