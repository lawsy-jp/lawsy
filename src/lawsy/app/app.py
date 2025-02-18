import os
import time
from pathlib import Path
import base64

import dotenv
import streamlit as st
from loguru import logger

from lawsy.app.config import create_config_page, init_config
from lawsy.app.page import PAGES, create_lawsy_page
from lawsy.app.utils.cookie import get_user_id, init_cookies
from lawsy.app.utils.history import get_history
from lawsy.app.utils.preload import (
    load_tavily_search_web_retriever,
    load_text_encoder,
    load_vector_search_article_retriever,
)

dotenv.load_dotenv()
data_dir = Path(os.getenv("DATA_DIR", Path(__file__).parent.parent.parent.parent / "data"))
output_dir = Path(os.getenv("OUTPUT_DIR", Path(__file__).parent.parent.parent.parent / "outputs"))
icon_path = Path(__file__).parent / "Lawsy_logo_circle.png"
logo_path = Path(__file__).parent / "Lawsy_logo_title_long.png"

st.set_page_config(page_title="Lawsy", layout="wide", page_icon=str(icon_path))


def get_base64_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode()
logo_base64 = get_base64_image(logo_path)

st.markdown(
    f"""
    <style>
    [data-testid="stSidebarHeader"]::before {{
        content: " ";
        display: block;
        width: 350px;
        height: 80px;
        background-image: url("data:image/png;base64,{logo_base64}");
        background-size: contain;
        background-repeat: no-repeat;
        background-position: center;
    }}
    </style>
    """,
    unsafe_allow_html=True
)

init_cookies()
# loading cookie might require about 2 sec to sync, so we execute time-consuming preload here
# cx) https://www.reddit.com/r/Streamlit/comments/1fdm1pj/persisting_session_state_data_across_browser/
tic = time.time()
text_encoder = load_text_encoder()
vector_search_article_retriever = load_vector_search_article_retriever()
tavily_search_web_retriever = load_tavily_search_web_retriever()
tac = time.time()
if tac - tic < 3:
    with st.spinner("loading cookies..."):
        time.sleep(tac - tic)

user_id = get_user_id()
logger.info(f"user_id: {user_id}")

init_config()

history = get_history(user_id)
if history:
    logger.info("history:\n" + "\n".join(["- " + report.title for report in history]))
else:
    logger.info("no history")
for report in history:
    PAGES[report.id] = st.Page(create_lawsy_page(report), title=report.title, url_path=report.id)

pages = {
    "New": [st.Page(create_lawsy_page(), title="New Research", url_path="new", icon=":material/edit_square:")],
    "Config": [st.Page(create_config_page, title="Config", url_path="config", icon=":material/settings:")],
    "History": [PAGES[report.id] for report in history],
}
pg = st.navigation(pages, expanded=True)
# hack for always displaying navigation
if len(history) > 0:
    with st.sidebar:
        st.empty()
pg.run()
