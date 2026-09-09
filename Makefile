.PHONY: setup up down logs migrate seed train forecast score simulate demo test clean create-admin backfill-live pipeline-cycle bootstrap-evaluation-history

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

create-admin:
	$(BACKEND) python -m app.tasks.bootstrap_admin

backfill-live:
	$(BACKEND) python -m app.tasks.backfill_live

pipeline-cycle:
	$(BACKEND) python -m app.tasks.hourly_pipeline --region nyiso-live

bootstrap-evaluation-history:
	$(BACKEND) python -m app.tasks.bootstrap_evaluation_history --region nyiso-live

test:
	$(BACKEND) pytest -v

clean:
	$(COMPOSE) down -v
	rm -rf data/models/*.joblib
