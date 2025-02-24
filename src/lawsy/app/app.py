import os
from pathlib import Path

import dotenv
import streamlit as st

from lawsy.app.config import create_config_page, get_config, init_config
from lawsy.app.report import REPORT_PAGES, create_report_page
from lawsy.app.research import create_research_page
from lawsy.app.utils.history import get_history
from lawsy.app.utils.preload import (
    load_text_encoder,
    load_vector_search_article_retriever,
)
from lawsy.utils.logging import logger

dotenv.load_dotenv()
data_dir = Path(os.getenv("LAWSY_DATA_DIR", "data"))
output_dir = Path(os.getenv("LAWSY_OUTPUT_DIR", "outputs"))
icon_path = Path(__file__).parent / "Lawsy_logo_circle.png"

st.set_page_config(page_title="Lawsy", layout="wide", page_icon=str(icon_path))

text_encoder = load_text_encoder()
vector_search_article_retriever = load_vector_search_article_retriever()

init_config()

history = get_history(get_config("history_dir"))
if history:
    logger.info("history:\n" + "\n".join(["- " + report.title for report in history]))
else:
    logger.info("no history")
for report in history:
    REPORT_PAGES[report.id] = st.Page(create_report_page(report), title=report.title, url_path=report.id)

pages = {
    "New": [st.Page(create_research_page, title="New Research", url_path="new", icon=":material/edit_square:")],
    "Config": [st.Page(create_config_page, title="Config", url_path="config", icon=":material/settings:")],
    "History": [REPORT_PAGES[report.id] for report in history],
}
pg = st.navigation(pages, expanded=True)
# hack for always displaying navigation
if len(history) > 0:
    with st.sidebar:
        st.empty()
pg.run()
