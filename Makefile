.PHONY: help install dev-install compile-deps update-deps clean test test-unit test-integration test-e2e lint format type-check setup-dev

# Default target
help:
	@echo "Available commands:"
	@echo "  install         Install production dependencies"
	@echo "  dev-install     Install development dependencies" 
	@echo "  compile-deps    Compile requirements files"
	@echo "  update-deps     Update and compile requirements files"
	@echo "  clean           Clean up cache and temporary files"
	@echo "  test            Run all tests"
	@echo "  test-unit       Run unit tests only"
	@echo "  test-integration Run integration tests only"
	@echo "  test-e2e        Run end-to-end tests only"
	@echo "  lint            Run linting checks"
	@echo "  format          Format code"
	@echo "  type-check      Run type checking"
	@echo "  setup-dev       Set up development environment"

# Dependency management
compile-deps:
	@echo "Compiling requirements..."
	pip-compile requirements/base.in
	pip-compile requirements/dev.in

update-deps:
	@echo "Updating and compiling requirements..."
	pip-compile --upgrade requirements/base.in
	pip-compile --upgrade requirements/dev.in

install:
	@echo "Installing production dependencies..."
	pip install -r requirements/base.txt

dev-install:
	@echo "Installing development dependencies..."
	pip install -r requirements/base.txt -r requirements/dev.txt
	pip install -e .

# Testing
test:
	@echo "Running all tests..."
	python -m pytest tests/ -v

test-unit:
	@echo "Running unit tests..."
	python -m pytest tests/unit/ -v

test-integration:
	@echo "Running integration tests..."
	python -m pytest tests/integration/ -v

test-e2e:
	@echo "Running end-to-end tests..."
	python -m pytest tests/e2e/ -v

test-coverage:
	@echo "Running tests with coverage..."
	python -m pytest tests/ --cov=src/aether_frame --cov-report=html --cov-report=term-missing

# Code quality
lint:
	@echo "Running linting checks..."
	flake8 src/ tests/
	black --check src/ tests/
	isort --check-only src/ tests/

format:
	@echo "Formatting code..."
	black src/ tests/
	isort src/ tests/

type-check:
	@echo "Running type checks..."
	mypy src/aether_frame/

# Development setup
setup-dev: dev-install
	@echo "Setting up development environment..."
	@if [ ! -f .env ]; then cp .env.example .env; echo "Created .env file from template"; fi
	@mkdir -p logs
	@echo "Development environment ready!"

# Cleanup
clean:
	@echo "Cleaning up..."
	find . -type d -name "__pycache__" -delete
	find . -name "*.pyc" -delete
	find . -name "*.pyo" -delete
	find . -name "*.orig" -delete
	find . -name ".coverage" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -exec rm -rf {} +
	rm -rf build/
	rm -rf dist/
	rm -rf htmlcov/

# Docker (for future use)
docker-build:
	@echo "Building Docker image..."
	docker build -t aether-frame .

docker-run:
	@echo "Running Docker container..."
	docker run --rm -it --env-file .env aether-frame

# Documentation
docs:
	@echo "Generating documentation..."
	# Add documentation generation command here when needed

# Version management
version:
	@echo "Current version: $(shell python -c 'import sys; sys.path.append("src"); from aether_frame import __version__; print(__version__)')"