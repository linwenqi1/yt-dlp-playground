.PHONY: setup dev-backend dev-frontend test lint format build check docker-build docker-up docker-logs docker-down

setup:
	cd backend && uv sync
	cd frontend && pnpm install

dev-backend:
	cd backend && uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

dev-frontend:
	cd frontend && pnpm dev

test:
	cd backend && uv run pytest

lint:
	cd backend && uv run ruff check .
	cd backend && uv run ruff format --check .
	cd frontend && pnpm typecheck

format:
	cd backend && uv run ruff check --fix .
	cd backend && uv run ruff format .

build:
	cd frontend && pnpm build

check: lint test build

docker-build:
	docker build -t ytp-backend:dev backend

docker-up:
	docker compose -f deploy/docker-compose.yml up -d backend

docker-logs:
	docker compose -f deploy/docker-compose.yml logs -f backend

docker-down:
	docker compose -f deploy/docker-compose.yml down
