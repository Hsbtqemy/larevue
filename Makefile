PYTHON    = python3
VENV      = .venv
PIP       = $(VENV)/bin/pip
MANAGE    = $(VENV)/bin/python manage.py
PYTEST    = $(VENV)/bin/pytest
RUFF      = $(VENV)/bin/ruff
PRECOMMIT = $(VENV)/bin/pre-commit

.PHONY: venv install test run migrate makemigrations lint format shell superuser

venv:
	$(PYTHON) -m venv $(VENV)

install: venv
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements/development.txt
	$(PRECOMMIT) install
	@echo "\n✓ Environnement prêt. Copie .env.example vers .env et configure la base de données."

test:
	$(PYTEST)

run:
	$(MANAGE) runserver

migrate:
	$(MANAGE) migrate

makemigrations:
	$(MANAGE) makemigrations

lint:
	$(RUFF) check .

format:
	$(RUFF) format .

shell:
	$(MANAGE) shell_plus

superuser:
	$(MANAGE) createsuperuser
