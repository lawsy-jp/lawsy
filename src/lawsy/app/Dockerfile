FROM python:3.12-slim

# install basic libs
ENV DEBIAN_FRONTEND=noninteractive

ARG WORKDIR="/app"
ENV WORKDIR=${WORKDIR}
WORKDIR /app

RUN pip install uv
COPY pyproject.toml pyproject.toml
RUN uv sync --no-dev --no-python-downloads --no-cache
ENV PATH="/app/.venv/bin:$PATH"

ENV HF_HOME="/app/cache/"
# uncomment if you use ME5 model
# COPY ./cache/hub/models--intfloat--multilingual-e5-large-instruct /app/cache/hub/models--intfloat--multilingual-e5-large-instruct
COPY ./outputs/lawsy/article_chunks_faiss /app/outputs/lawsy/article_chunks_faiss
COPY .env /app/.env
COPY .streamlit/config.toml /app/.streamlit/config.toml

ARG PORT="8501"
ENV PORT=${PORT}
EXPOSE ${PORT}

COPY ./src ./src
COPY ./Makefile ./Makefile
ENV PYTHONPATH=src

CMD ["streamlit", "run", "src/lawsy/app/app.py"]
