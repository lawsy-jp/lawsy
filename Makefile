-include .env  # load .env if it exists

LAWSY_DATA_DIR ?= ./data
LAWSY_OUTPUT_DIR ?= ./outputs # set OUTPUT_DIR=./outputs if it's unset
LAWSY_ENCODER_MODEL_NAME ?= openai/text-embedding-3-small
LAWSY_ENCODER_DIM ?= 512
LAWSY_PREPROCESSED_DATA_VERSION ?= latest


# Setup --------------------------------------------------------------------------
.PHONY: activate install


activate:
	. .venv/bin/activate


deactivate:
	deactivate


install:
	@uv sync --all-groups


# Formatter / Linter / Test ------------------------------------------------------
.PHONY: format lint


format:
	@PATH=".venv/bin:${PATH}" ruff format


lint:
	@PATH=".venv/bin:${PATH}" ruff check src
	@PATH=".venv/bin:${PATH}" pyright src


# Docker -------------------------------------------------------------------------
.PHONY: docker-login


docker-login:
	@gcloud auth print-access-token | docker login -u oauth2accesstoken https://asia-northeast1-docker.pkg.dev --password-stdin


# Lawsy --------------------------------------------------------------------------
.PHONY:	lawsy-download-preprocessed-data \
        lawsy-create-article-chunks \
        lawsy-embed-article-chunks \
		lawsy-create-article-chunk-vector-index \
		lawsy-prepare \
        lawsy-run-app \
		lawsy-docker-build-app \
		lawsy-docker-push-app \
		lawsy-docker-run-app


lawsy-download-preprocessed-data:
	@mkdir -p outputs && gcloud storage cp -r gs://885188444194-public-data/${LAWSY_PREPROCESSED_DATA_VERSION}/lawsy ./outputs/


lawsy-create-article-chunks:
	@PATH=".venv/bin:${PATH}" PYTHONPATH=src python src/lawsy/main.py create-article-chunks $(shell echo ${LAWSY_DATA_DIR})/all_xml $(shell echo ${LAWSY_OUTPUT_DIR})/lawsy/article_chunks.jsonl


lawsy-embed-article-chunks:
	@PATH=".venv/bin:${PATH}" PYTHONPATH=src python src/lawsy/main.py embed-article-chunks $(shell echo ${LAWSY_OUTPUT_DIR})/lawsy/article_chunks.jsonl $(shell echo ${LAWSY_OUTPUT_DIR})/lawsy/article_chunk_embeddings.parquet --model_name ${LAWSY_ENCODER_MODEL_NAME}


lawsy-create-article-chunk-vector-index:
	@PATH=".venv/bin:${PATH}" PYTHONPATH=src python src/lawsy/main.py create-article-chunk-vector-index $(shell echo ${LAWSY_OUTPUT_DIR})/lawsy/article_chunk_embeddings.parquet $(shell echo ${LAWSY_OUTPUT_DIR})/lawsy/article_chunks.jsonl $(shell echo ${LAWSY_OUTPUT_DIR})/lawsy/article_chunks_faiss --dim ${LAWSY_ENCODER_DIM}


lawsy-prepare: lawsy-create-article-chunks lawsy-embed-article-chunks lawsy-create-article-chunk-vector-index


lawsy-run-app:
	@PATH=".venv/bin:${PATH}" PYTHONPATH=src LAWSY_OUTPUT_DIR=${LAWSY_OUTPUT_DIR} streamlit run src/lawsy/app/app.py


lawsy-docker-build-app:
	@docker build --platform=linux/amd64 -t lawsy-app -f src/lawsy/app/Dockerfile .


lawsy-docker-push-app: docker-login
	@docker build --platform=linux/amd64 -t asia-northeast1-docker.pkg.dev/law-dx-hackathon-2025/lawsy/lawsy-app:latest -f src/lawsy/app/Dockerfile . --push


lawsy-docker-run-app:
	@docker run -it --rm --name lawsy-app \
	    -v ./src:/app/src \
		-v ./.env:/app/.env \
		-v ./.streamlit:/app/.streamlit \
		-v ./lawsy_history:/app/lawsy_history \
		-v ./outputs:/app/outputs \
		-p 8501:8501 lawsy-app:latest
