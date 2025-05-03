FROM ghcr.io/didx-xyz/acapy-agent:py3.12-test-1.3.0rc2-20250503

USER root

# Install Google Protobuf and Plugins
ARG PROTOBUF_VERSION=5.29.3
RUN pip install --no-cache-dir protobuf==${PROTOBUF_VERSION} \
  # acapy-wallet-groups-plugin==1.3.0rc1.post20250417 \
  git+https://github.com/didx-xyz/acapy-wallet-groups-plugin@make-acapy-optional \
  git+https://github.com/didx-xyz/aries-acapy-plugins@make-acapy-optional#subdirectory=nats_events

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
