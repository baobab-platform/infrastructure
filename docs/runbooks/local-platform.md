# Local platform runbook

## Purpose

Foundation 1 supplies the local infrastructure dependencies for later
`baobab-cp` development. It does not provision production infrastructure and it
does not include the control-plane application.

For how this topology fits multi-engine integrated testing, see
[docs/testing/platform-integrated-testing-strategy.md](../testing/platform-integrated-testing-strategy.md)
and [docs/testing/platform-test-topology.md](../testing/platform-test-topology.md).

## Prerequisites

- Docker Engine with Compose v2
- at least 4 CPU cores, 8 GB RAM, and 10 GB free storage
- ports `4317`, `4318`, `5432`, `5672`, `6379`, `9080`, `9180`, `13133`, and
  `15672` available on loopback

## Start and verify

```bash
make local-env
```

Replace every placeholder in `compose/.env`, then run:

```bash
make local-verify
```

The verification command validates the resolved Compose model, waits for the
stateful services and APISIX, then checks the APISIX Admin API, RabbitMQ
readiness endpoint, and OpenTelemetry health endpoint from inside the isolated
networks.

For non-interactive / CI-style placeholders (not for day-to-day development):

```bash
make ci-env
make local-verify
```

Useful commands:

```bash
make local-ps
make local-logs
make local-down
```

`make local-down` preserves named volumes. To destroy local data deliberately,
run `docker compose --env-file compose/.env -f compose/compose.yaml down -v`
after confirming that the `nabhold-platform` project is the intended target.

## Local endpoints

All published ports bind to `127.0.0.1`; none listens on every host interface.

| Service | Endpoint |
| --- | --- |
| APISIX gateway | `http://127.0.0.1:9080` |
| APISIX Admin API | `http://127.0.0.1:9180` |
| PostgreSQL | `127.0.0.1:5432` |
| RabbitMQ AMQP | `amqp://127.0.0.1:5672` |
| RabbitMQ management | `http://127.0.0.1:15672` |
| Redis | `redis://127.0.0.1:6379` |
| OTLP gRPC | `127.0.0.1:4317` |
| OTLP HTTP | `http://127.0.0.1:4318` |

## Security boundary

The committed environment file contains placeholders, not usable credentials.
etcd is intentionally unauthenticated only inside the internal `control`
network and has no published host port. APISIX Admin access requires the local
key and is restricted to loopback and the dedicated control subnet.

This is a developer topology, not a production template. Production requires
TLS, managed secrets, multi-AZ persistence, backups, workload identity, remote
state, monitoring, and approved recovery objectives.

## Troubleshooting

Inspect status and bounded logs first:

```bash
make local-ps
docker compose --env-file compose/.env -f compose/compose.yaml logs --tail=200 SERVICE
```

If a service was initialised with old credentials, changing `compose/.env` does
not rewrite its persistent volume. Confirm the project and volume names before
performing any data-destroying reset.
