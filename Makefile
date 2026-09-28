.PHONY: dev test test-unit test-integration lint typecheck fmt migrate migration logs down build

dev:
	docker compose up -d --build
	docker compose logs -f bot worker

build:
	docker compose build

down:
	docker compose down

logs:
	docker compose logs -f

test: test-unit test-integration

test-unit:
	pytest tests/unit -v

test-integration:
	pytest tests/integration -v -m integration

lint:
	ruff check app tests
	mypy app

fmt:
	ruff check --fix app tests
	ruff format app tests

migrate:
	alembic upgrade head

migration:
	@read -p "Migration message: " msg; \
	alembic revision --autogenerate -m "$$msg"
