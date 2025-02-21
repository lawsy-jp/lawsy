import os
import time
from pathlib import Path

import dotenv
import streamlit as st
from loguru import logger

from lawsy.app.config import create_config_page, init_config
from lawsy.app.report import REPORT_PAGES, create_report_page
from lawsy.app.research import create_research_page
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

st.set_page_config(page_title="Lawsy", layout="wide", page_icon=str(icon_path))

# streamlit-cookie-controllerが意図せず空白スペースを作ってしまうのでそれを非表示する
# https://github.com/NathanChen198/streamlit-cookies-controller/issues/8#issuecomment-2594580956
st.markdown(
    # f-stringではなくすると機能しなくなるので注意（なぜ…）
    f"""
        <style>
            .element-container:has(
                iframe[height="0"]
            ):has(
                iframe[title="streamlit_cookies_controller.cookie_controller.cookie_controller"]
            ) {{
            display: none;
            }}
        </style>
    """,  # noqa: F541
    unsafe_allow_html=True,
)
init_cookies()
# loading cookie could require about 2 sec to sync, so we preload big assets here
# cx) https://www.reddit.com/r/Streamlit/comments/1fdm1pj/persisting_session_state_data_across_browser/
tic = time.time()
text_encoder = load_text_encoder()
vector_search_article_retriever = load_vector_search_article_retriever()
tavily_search_web_retriever = load_tavily_search_web_retriever()

tac = time.time()
if tac - tic < 5:
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
