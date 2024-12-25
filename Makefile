-include .env  # load .env if it exists

OUTPUT_DIR ?= ./outputs # set OUTPUT_DIR=./outputs if it's unset
PYTHON := . .venv/bin/activate && python
RUFF := . .venv/bin/activate && ruff
PYRIGHT := . .venv/bin/activate && pyright


# Setup --------------------------------------------------------------------------
.PHONY: activate install


activate:
	. .venv/bin/activate


install:
	uv sync --all-groups


# Formatter / Linter / Test ------------------------------------------------------
.PHONY: format lint


format:
	${RUFF} format


lint:
	${RUFF} check src
	${PYRIGHT} src


# Kokkai Crawler -----------------------------------------------------------------
.PHONY: crawl-all


crawl-all:
	${PYTHON} src/kokkai_crawler/main.py $(shell echo ${OUTPUT_DIR})/data/kokkai/mtgs.jsonl --from-year 1945
