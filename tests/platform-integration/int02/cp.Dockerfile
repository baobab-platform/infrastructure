# INT-02 CP binary and migration built at exactly the pinned baobab-cp SHA.
# No test hooks, shadow auth or mock CP binaries are permitted.
FROM golang:1.27.2-bookworm AS builder
WORKDIR /src
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 go build -trimpath -o /out/controlplane ./cmd/controlplane && \
    CGO_ENABLED=0 go build -trimpath -o /out/migrate ./cmd/migrate
FROM gcr.io/distroless/static-debian13:nonroot
COPY --from=builder /out/controlplane /controlplane
COPY --from=builder /out/migrate /migrate
USER nonroot:nonroot
ENTRYPOINT ["/controlplane"]
