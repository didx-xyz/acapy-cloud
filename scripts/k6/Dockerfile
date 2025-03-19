FROM docker.io/golang:1.23 AS builder

WORKDIR /app

RUN go install go.k6.io/xk6/cmd/xk6@v0.13.4
RUN xk6 build v0.56.0 --output /app/xk6 \
  --with github.com/avitalique/xk6-file@v1.4.2 \
  --with github.com/phymbert/xk6-sse@v0.1.8 \
  --with github.com/LeonAdato/xk6-output-statsd@latest

FROM docker.io/alpine:3
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
