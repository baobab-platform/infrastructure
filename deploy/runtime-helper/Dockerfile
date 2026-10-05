FROM golang:1.27.0-alpine@sha256:4c9fe60190a2a3350ddc51de80d0224b8a6698d12bdfc999fee45ea9d6c46dbc AS build
WORKDIR /src
COPY go.mod go.sum ./
RUN go mod download
COPY deploy/runtime-helper/main.go ./deploy/runtime-helper/main.go
RUN CGO_ENABLED=0 go build -trimpath -ldflags='-s -w' -o /runtime-helper ./deploy/runtime-helper
FROM scratch
ARG VERSION=0.0.0-dev
ARG REVISION=unknown
LABEL org.opencontainers.image.source="https://github.com/baobab-platform/infrastructure" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.revision="${REVISION}"
COPY --from=build /runtime-helper /runtime-helper
COPY --from=build /etc/ssl/certs/ca-certificates.crt /etc/ssl/certs/ca-certificates.crt
USER 65532:65532
HEALTHCHECK --interval=30s --timeout=6s --start-period=30s --retries=3 CMD ["/runtime-helper", "-mode=probe", "-url=https://127.0.0.1:8443/_transport/health", "-server-name=cp.staging.baobab.internal", "-cert=/run/baobab/probe.pem", "-key=/run/baobab/probe.key"]
ENTRYPOINT ["/runtime-helper"]
