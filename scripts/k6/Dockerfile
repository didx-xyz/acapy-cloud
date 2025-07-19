FROM docker.io/golang:1.24-alpine@sha256:68932fa6d4d4059845c8f40ad7e654e626f3ebd3706eef7846f319293ab5cb7a AS builder

WORKDIR /app

RUN apk add --update --no-cache git

RUN go install go.k6.io/xk6/cmd/xk6@v0.19.3
RUN xk6 build v1.0.0 --output /app/xk6 \
  --with github.com/avitalique/xk6-file@v1.5.0 \
  --with github.com/phymbert/xk6-sse@v0.1.9 \
  --with github.com/LeonAdato/xk6-output-statsd@v0.2.1

###

FROM docker.io/alpine:3@sha256:4bcff63911fcb4448bd4fdacec207030997caf25e9bea4045fa6c8c44de311d1 AS k6

RUN apk add --update --no-cache bash tini

COPY --from=builder /app/xk6 /usr/local/bin/xk6

USER nobody
WORKDIR /k6

COPY --chown=nobody:nobody scripts /k6/scripts
COPY --chown=nobody:nobody scenarios /k6/scenarios
COPY --chown=nobody:nobody libs /k6/libs

ENTRYPOINT ["/bin/bash"]
