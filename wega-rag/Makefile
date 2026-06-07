.PHONY: help dev build deploy lint test

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

dev: ## Run app locally with uvicorn (reload)
	uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload

build: ## Build Docker image locally
	docker build -t sdlc-kb .

deploy: ## Deploy to Cloud Run
	gcloud run deploy dev-wega-rag-agent --source . \
		--service-account=sa-cloudrun@digital-rig-poc.iam.gserviceaccount.com \
		--region=us-central1 --min-instances=0 --max-instances=3 \
		--port=8080 --allow-unauthenticated --timeout=900 --memory=4Gi --cpu=2

lint: ## Run ruff linter
	ruff check app/

test: ## Run pytest
	pytest tests/ -v --tb=short
