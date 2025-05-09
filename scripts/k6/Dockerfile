FROM docker.io/golang:1.24-alpine@sha256:ef18ee7117463ac1055f5a370ed18b8750f01589f13ea0b48642f5792b234044 AS builder

WORKDIR /app

RUN apk add --update --no-cache git

RUN go install go.k6.io/xk6/cmd/xk6@v0.19.2
RUN xk6 build v1.0.0 --output /app/xk6 \
  --with github.com/avitalique/xk6-file@v1.5.0 \
  --with github.com/phymbert/xk6-sse@v0.1.9 \
  --with github.com/LeonAdato/xk6-output-statsd@v0.2.1

###

FROM docker.io/alpine:3@sha256:a8560b36e8b8210634f77d9f7f9efd7ffa463e380b75e2e74aff4511df3ef88c AS k6

RUN apk add --update --no-cache bash tini

COPY --from=builder /app/xk6 /usr/local/bin/xk6

USER nobody
WORKDIR /k6

COPY --chown=nobody:nodody scripts /k6/scripts
COPY --chown=nobody:nodody scenarios /k6/scenarios
COPY --chown=nobody:nodody libs /k6/libs
COPY --chown=nobody:nodody env.sh /k6/env.sh

ENTRYPOINT ["/bin/bash"]
