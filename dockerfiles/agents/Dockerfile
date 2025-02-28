ARG BBS_SUFFIX="-bbs"
FROM ghcr.io/didx-xyz/acapy-agent${BBS_SUFFIX}:py3.12-1.2.1-20250227

USER root

# Install Google Protobuf and Plugins
ARG PROTOBUF_VERSION=5.29.3
RUN pip install --no-cache-dir protobuf==${PROTOBUF_VERSION} \
  git+https://github.com/didx-xyz/acapy-wallet-groups-plugin@8eea55929c03695f1eed3aec3232438271e9cf69 \
  git+https://github.com/didx-xyz/aries-acapy-plugins@590ce0d955a9b0f83c2079187cb1d9fd28a12f42#subdirectory=nats_events

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
