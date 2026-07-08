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

# Host port published by this Docker stack (web). `make kill` releases the stack's
# own containers (so a re-`up` can rebind the port) and warns if a NON-Docker process
# is squatting the port — it never kills foreign processes for you.
HOST_PORTS := 8000

# Local-dev admin (override on the command line, e.g. `make superuser SU_PASS=…`).
SU_USER  ?= admin
SU_EMAIL ?= admin@cmstack.local
SU_PASS  ?= admin12345

.DEFAULT_GOAL := help
.PHONY: help dev up down reset logs seed seed_demo migrate test kill clean superuser shell

help: ## List available targets
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) \
	  | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

dev: up seed ## One-shot local dev: build+start (auto-migrates), create admin, seed demo content, follow logs
	@echo "web: http://localhost:8000  (admin: $(SU_USER) / $(SU_PASS))"
	$(COMPOSE) logs -f web

up: kill ## Build and start the stack; the entrypoint runs migrations on boot
	$(COMPOSE) up -d --build
	@echo "waiting for the web service…"
	@until curl -sf http://localhost:8000/ >/dev/null 2>&1; do sleep 2; done
	@echo "web up"

migrate: ## Apply migrations manually (also runs automatically on boot)
	$(WEB) python manage.py migrate --noinput

seed: superuser seed_demo ## Seed idempotent local data (admin superuser + demo content)

seed_demo: ## Seed idempotent demo content (categories, posts, About/Contact pages)
	$(WEB) python manage.py seed_demo

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

kill: ## Release this stack's host ports (down its own containers; warn on foreign holders)
	@$(COMPOSE) down --remove-orphans 2>/dev/null || true
	@for p in $(HOST_PORTS); do \
	  pid=$$(lsof -ti:$$p -sTCP:LISTEN 2>/dev/null); \
	  if [ -n "$$pid" ]; then \
	    echo "⚠ port $$p still held by a non-Docker process (PID $$pid) — free it with: kill $$pid"; \
	  fi; \
	done

down: ## Stop all containers (keeps the DB volume)
	$(COMPOSE) down

reset: ## Wipe the DB volume and re-bootstrap from scratch
	$(COMPOSE) down -v
	$(MAKE) dev

clean: ## Stop the stack AND remove the DB volume (destroys data)
	$(COMPOSE) down -v
