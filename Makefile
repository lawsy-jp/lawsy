-include .env  # load .env if it exists

OUTPUT_DIR ?= ./outputs # set OUTPUT_DIR=./outputs if it's unset

# Setup --------------------------------------------------------------------------
.PHONY: activate install


activate:
	. .venv/bin/activate


install:
	uv sync --all-groups


# Formatter / Linter / Test ------------------------------------------------------
.PHONY: format lint


format: activate
	ruff format


lint: activate
	ruff check src
	pyright src


# Kokkai Crawler -----------------------------------------------------------------
.PHONY: crawl-all


crawl-all: activate
	python src/kokkai_crawler/main.py $(shell echo ${OUTPUT_DIR})/data/kokkai/mtgs.jsonl --from-year 1945
