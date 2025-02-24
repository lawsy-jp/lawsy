import json
import os
from pathlib import Path

import dotenv
import streamlit as st

from lawsy.encoder.me5 import ME5Instruct
from lawsy.encoder.openai import OpenAITextEmbedding
from lawsy.retriever.article_search.faiss import FaissFlatArticleRetriever
from lawsy.utils.logging import logger

dotenv.load_dotenv()
output_dir = Path(os.getenv("LAWSY_OUTPUT_DIR", "outputs"))


@st.cache_resource
def load_article_chunks() -> dict:
    with st.spinner("loading article chunks..."):
        logger.info("loading article chunks")
        result = {}
        with open(output_dir / "lawsy" / "article_chunks.jsonl") as fin:
            for line in fin:
                d = json.loads(line)
                key = (d["file_name"], d["anchor"])
                result[key] = d
        return result


@st.cache_resource
def load_text_encoder(dim: int | None = None) -> ME5Instruct | OpenAITextEmbedding:
    with st.spinner("loading text encoder..."):
        logger.info("loading text encoder...")
        model_name = os.getenv("LAWSY_ENCODER_MODEL_NAME")
        prefix = model_name.split("/")[0] if model_name is not None else None
        if model_name is None or prefix == "openai":
            return OpenAITextEmbedding(dim=dim)
        else:
            return ME5Instruct()


@st.cache_resource
def load_vector_search_article_retriever() -> FaissFlatArticleRetriever:
    with st.spinner("loading vector search article retriever..."):
        logger.info("loading vector search article retriever...")
        return FaissFlatArticleRetriever.load(output_dir / "lawsy" / "article_chunks_faiss")
