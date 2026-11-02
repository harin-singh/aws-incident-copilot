.PHONY: help install install-dev lint format test test-cov demo clean pre-commit terraform-validate

PYTHON := python3
PIP := $(PYTHON) -m pip

help: ## Show this help message
	@echo "AWS Incident Copilot - Development Commands"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

install: ## Install package in production mode
	$(PIP) install -e .

install-dev: ## Install package with development dependencies
	$(PIP) install -e ".[dev]"
	pre-commit install

lint: ## Run linting checks (ruff + mypy)
	ruff check src/ tests/
	ruff format --check src/ tests/
	mypy src/

format: ## Auto-format code with ruff
	ruff format src/ tests/
	ruff check --fix src/ tests/

test: ## Run tests
	pytest tests/ -v

test-unit: ## Run unit tests only
	pytest tests/ -v -m unit

test-cov: ## Run tests with coverage report
	pytest tests/ --cov=aws_incident_copilot --cov-report=term-missing --cov-report=html

demo: ## Run the demo mode with sample incident
	$(PYTHON) -m aws_incident_copilot.cli demo --scenario crashloop

demo-all: ## Run all demo scenarios
	@echo "=== Scenario 1: EKS CrashLoopBackOff ==="
	$(PYTHON) -m aws_incident_copilot.cli demo --scenario crashloop
	@echo ""
	@echo "=== Scenario 2: ECS OOM Kill ==="
	$(PYTHON) -m aws_incident_copilot.cli demo --scenario oom
	@echo ""
	@echo "=== Scenario 3: ALB 5xx Spike ==="
	$(PYTHON) -m aws_incident_copilot.cli demo --scenario alb-5xx

clean: ## Clean build artifacts and caches
	rm -rf build/ dist/ *.egg-info/
	rm -rf .pytest_cache/ .mypy_cache/ .ruff_cache/
	rm -rf htmlcov/ .coverage coverage.xml
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true

pre-commit: ## Run pre-commit on all files
	pre-commit run --all-files

terraform-validate: ## Validate Terraform configuration
	cd terraform && terraform init -backend=false && terraform validate && terraform fmt -check -recursive

terraform-fmt: ## Format Terraform files
	cd terraform && terraform fmt -recursive

security-scan: ## Run security scans (gitleaks, checkov)
	gitleaks detect --source . --verbose
	checkov -d terraform/ --framework terraform

deps-audit: ## Audit dependencies for vulnerabilities
	$(PIP) install pip-audit
	pip-audit

# Live mode commands (require AWS credentials)
live-deploy: ## Deploy infrastructure with Terraform
	@echo "Deploying AWS infrastructure..."
	cd terraform && terraform init && terraform apply

live-destroy: ## Destroy all deployed infrastructure
	@echo "WARNING: This will destroy all deployed resources!"
	cd terraform && terraform destroy

live-run: ## Run incident copilot in live mode
	$(PYTHON) -m aws_incident_copilot.cli run --mode live
