.DEFAULT_GOAL := help
COMPOSE := docker compose

help: ## show targets
	@grep -hE '^[a-z-]+:.*##' $(MAKEFILE_LIST) | sed 's/:.*##/\t/' | expand -t22

up: ## build and start the whole stack
	$(COMPOSE) up --build -d
	@echo "api      http://localhost:8000/docs"
	@echo "web      http://localhost:5173"
	@echo "mailhog  http://localhost:8025"

down: ## stop the stack
	$(COMPOSE) down

logs: ## follow api + worker logs
	$(COMPOSE) logs -f api worker

migrate: ## apply migrations
	$(COMPOSE) run --rm api alembic upgrade head

revision: ## autogenerate a migration: make revision m="add x"
	$(COMPOSE) run --rm api alembic revision --autogenerate -m "$(m)"

seed: ## fetch the top-50 coin list once (needs COINGECKO key or public rate limit)
	$(COMPOSE) run --rm api python -m app.workers.oneshot sync_coins

test: ## backend tests
	$(COMPOSE) run --rm api pytest -q

lint: ## ruff + mypy
	$(COMPOSE) run --rm api ruff check app tests
	$(COMPOSE) run --rm api mypy app

state: ## refresh docs/PROJECT_STATE.md
	python3 scripts/update_project_state.py

.PHONY: help up down logs migrate revision seed test lint state
