FROM docker.io/golang:1.24-alpine@sha256:2853d623ec1c92b54a34e783ce77ce354eb58e56979fe35c117bdaa45de12807 AS builder

WORKDIR /app

RUN apk add --update --no-cache git

RUN go install go.k6.io/xk6/cmd/xk6@v0.19.3
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

COPY --chown=nobody:nobody scripts /k6/scripts
COPY --chown=nobody:nobody scenarios /k6/scenarios
COPY --chown=nobody:nobody libs /k6/libs
COPY --chown=nobody:nobody env.sh /k6/env.sh

ENTRYPOINT ["/bin/bash"]
