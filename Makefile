# cmstack-django — local development helpers.
#
#   make dev     one command: build + start the stack (the entrypoint applies
#                migrations automatically), create a local admin, then follow logs.
#   make down    stop the containers.
#
# Run `make` (or `make help`) to list every target.

SHELL := /bin/bash
COMPOSE := docker compose
WEB := $(COMPOSE) exec -T web

# Local-dev admin (override on the command line, e.g. `make superuser SU_PASS=…`).
SU_USER  ?= admin
SU_EMAIL ?= admin@cmstack.local
SU_PASS  ?= admin12345

.DEFAULT_GOAL := help
.PHONY: help dev up down migrate superuser shell logs test reset

help: ## List available targets
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) \
	  | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-11s\033[0m %s\n", $$1, $$2}'

dev: up superuser ## One-shot local dev: build+start (auto-migrates), create admin, follow logs
	@echo "web: http://localhost:8000  (admin: $(SU_USER) / $(SU_PASS))"
	$(COMPOSE) logs -f web

up: ## Build and start the stack; the entrypoint runs migrations on boot
	$(COMPOSE) up -d --build
	@echo "waiting for the web service…"
	@until curl -sf http://localhost:8000/ >/dev/null 2>&1; do sleep 2; done
	@echo "web up"

migrate: ## Apply migrations manually (also runs automatically on boot)
	$(WEB) python manage.py migrate --noinput

superuser: ## Create an idempotent local admin superuser
	@$(COMPOSE) exec -T -e DJANGO_SUPERUSER_PASSWORD=$(SU_PASS) web \
	  python manage.py createsuperuser --noinput --username $(SU_USER) --email $(SU_EMAIL) \
	  2>/dev/null && echo "admin created" || echo "admin already exists (ok)"

shell: ## Open a shell in the web container
	$(COMPOSE) exec web bash

logs: ## Follow the web container logs
	$(COMPOSE) logs -f web

test: ## Run the test suite
	$(WEB) pytest

down: ## Stop all containers (keeps the DB volume)
	$(COMPOSE) down

reset: ## Wipe the DB volume and re-bootstrap from scratch
	$(COMPOSE) down -v
	$(MAKE) dev
