# INT-02 CP binary and migration built at exactly the pinned baobab-cp SHA.
# No test hooks, shadow auth or mock CP binaries are permitted.
# Both stages are pinned by reviewed digest (EA v2.2 §4.4 iv): tags are mutable.
FROM golang:1.27.2-bookworm@sha256:5cf287a799e6b94384bad13d16b14904c531f51ba65792237e122ce42b392f61 AS builder
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
