.PHONY: setup up down logs migrate seed train forecast score simulate demo test clean

COMPOSE = docker compose
BACKEND = $(COMPOSE) exec backend

setup:
	cp -n .env.example .env || true
	$(COMPOSE) build

up:
	$(COMPOSE) up -d
	@echo "Frontend: http://localhost:5173"
	@echo "Backend:  http://localhost:8000/docs"

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f

migrate:
	$(BACKEND) alembic upgrade head

seed:
	$(BACKEND) python -m app.ingestion.pipeline --region demo-region --days 180

train:
	$(BACKEND) python -m app.tasks.train_all --region demo-region

forecast:
	$(BACKEND) python -m app.tasks.generate_forecasts --region demo-region --horizon 24
	$(BACKEND) python -m app.tasks.generate_forecasts --region demo-region --horizon 48

score:
	$(BACKEND) python -m app.tasks.score_forecasts --region demo-region

simulate:
	$(BACKEND) python -m app.tasks.simulate_live --region demo-region --hours 72

demo:
	$(COMPOSE) up -d postgres backend
	$(BACKEND) alembic upgrade head
	$(BACKEND) python -m app.tasks.bootstrap_demo

test:
	$(BACKEND) pytest -v

clean:
	$(COMPOSE) down -v
	rm -rf data/models/*.joblib
