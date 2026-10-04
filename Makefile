SHELL := /bin/sh

COMPOSE := docker compose --env-file compose/.env -f compose/compose.yaml

.PHONY: local-config local-down local-env local-logs local-ps local-up local-verify ci-env

local-env:
	@test -f compose/.env || cp compose/.env.example compose/.env
	@echo "Local environment file is available at compose/.env"

# Deterministic placeholders for CI / non-interactive smoke (not for production).
ci-env:
	cp compose/.env.example compose/.env
	sed -i \
		-e 's/^APISIX_ADMIN_KEY=.*/APISIX_ADMIN_KEY=ci-apisix-admin-key-32chars-min-xx/' \
		-e 's/^POSTGRES_PASSWORD=.*/POSTGRES_PASSWORD=ci-postgres-password-32chars-min/' \
		-e 's/^RABBITMQ_DEFAULT_PASS=.*/RABBITMQ_DEFAULT_PASS=ci-rabbitmq-password-32chars-min/' \
		-e 's/^REDIS_PASSWORD=.*/REDIS_PASSWORD=ci-redis-password-32chars-minimum/' \
		compose/.env
	@echo "CI environment file written to compose/.env"

local-config:
	@test -f compose/.env || { echo "Run 'make local-env' first." >&2; exit 1; }
	$(COMPOSE) config --quiet

local-up: local-config
	$(COMPOSE) up -d --wait etcd postgresql rabbitmq redis otel-collector apisix

local-verify: local-config
	./scripts/verify-local.sh

local-ps:
	$(COMPOSE) ps

local-logs:
	$(COMPOSE) logs --follow --tail=200

local-down:
	$(COMPOSE) down --remove-orphans
