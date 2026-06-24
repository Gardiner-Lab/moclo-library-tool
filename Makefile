.PHONY: help setup install test test-cov run docker-build docker-up docker-down clean

help:
	@echo "MoClo Library Tool - Available Commands"
	@echo "========================================"
	@echo "setup        - Create virtual environment and install dependencies"
	@echo "install      - Install dependencies only"
	@echo "test         - Run all tests"
	@echo "test-cov     - Run tests with coverage report"
	@echo "run          - Run the Flask application locally"
	@echo "docker-build - Build Docker image"
	@echo "docker-up    - Start Docker container"
	@echo "docker-down  - Stop Docker container"
	@echo "clean        - Remove generated files and caches"

setup:
	python3 -m venv venv
	./venv/bin/pip install --upgrade pip
	./venv/bin/pip install -r requirements.txt
	mkdir -p data

install:
	./venv/bin/pip install -r requirements.txt

test:
	./venv/bin/pytest

test-cov:
	./venv/bin/pytest --cov=app --cov-report=html --cov-report=term

run:
	export FLASK_APP=app.main && \
	export DATABASE_PATH=./data/moclo.db && \
	export DYLD_LIBRARY_PATH=/opt/homebrew/lib:$$DYLD_LIBRARY_PATH && \
	./venv/bin/flask run

docker-build:
	docker-compose build

docker-up:
	docker-compose up

docker-down:
	docker-compose down

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".hypothesis" -exec rm -rf {} +
	find . -type d -name "htmlcov" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name ".coverage" -delete
	rm -rf venv
