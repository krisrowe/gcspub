.PHONY: setup test install clean

PYTHON ?= python3
VENV = .venv
VENV_BIN = $(VENV)/bin
PIP_ARGS = --index-url https://pypi.org/simple

$(VENV):
	$(PYTHON) -m venv $(VENV)
	$(VENV_BIN)/pip install $(PIP_ARGS) --upgrade pip setuptools wheel

setup: $(VENV)
	$(VENV_BIN)/pip install $(PIP_ARGS) -e .[dev]

test: setup
	$(VENV_BIN)/pytest

install:
	pipx install -e . --force --pip-args="$(PIP_ARGS)"

clean:
	rm -rf $(VENV)
	rm -rf *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} +
