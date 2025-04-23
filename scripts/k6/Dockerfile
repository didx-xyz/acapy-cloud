FROM docker.io/golang:1.23@sha256:e54daaadd35ebb90fc1404ecdc6eb7338ae13555f71a71856ad96976ae084e44 AS builder

WORKDIR /app

RUN go install go.k6.io/xk6/cmd/xk6@v0.13.4
RUN xk6 build v0.56.0 --output /app/xk6 \
  --with github.com/avitalique/xk6-file@v1.4.2 \
  --with github.com/phymbert/xk6-sse@v0.1.8 \
  --with github.com/LeonAdato/xk6-output-statsd@latest

FROM docker.io/alpine:3@sha256:a8560b36e8b8210634f77d9f7f9efd7ffa463e380b75e2e74aff4511df3ef88c
RUN apk add --no-cache bash

COPY --from=builder /app/xk6 /usr/local/bin/xk6

# Add Tini
ENV TINI_VERSION=v0.19.0
RUN apk add --no-cache tini

COPY scripts /k6/scripts
COPY scenarios /k6/scenarios
COPY libs /k6/libs
COPY env.sh /k6/env.sh

ENTRYPOINT ["/bin/bash"]
WORKDIR /k6

USER nobody
