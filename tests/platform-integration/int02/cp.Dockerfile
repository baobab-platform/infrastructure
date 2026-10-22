# INT-02 CP binary and migration built at exactly the pinned baobab-cp SHA.
# No test hooks, shadow auth or mock CP binaries are permitted.
# Both stages are pinned by reviewed digest (EA v2.2 §4.4 iv): tags are mutable.
# Reuse Infrastructure's verified supported Go 1.27.3 Alpine builder digest;
# CGO_ENABLED=0 makes the binaries independent of the build libc.
FROM golang:1.27.3-alpine@sha256:f2c872bcee949b7be9c490efd02b48a8a2fbf947cdf533f1c58525ec9d8170fd AS builder
WORKDIR /src
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 go build -trimpath -o /out/controlplane ./cmd/controlplane && \
    CGO_ENABLED=0 go build -trimpath -o /out/migrate ./cmd/migrate
FROM gcr.io/distroless/static-debian13:nonroot@sha256:e2e927ec666bae08560abb3c55d0659eceabb657f56b6782ab500a9fc7f555e3
COPY --from=builder /out/controlplane /controlplane
COPY --from=builder /out/migrate /migrate
USER nonroot:nonroot
ENTRYPOINT ["/controlplane"]
