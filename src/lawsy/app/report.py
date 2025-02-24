from pathlib import Path

import dotenv
import streamlit as st

from lawsy.app.styles.decorate_html import (
    embed_tooltips,
    get_hiddenbox_ref_html,
    get_reference_tooltip_html,
)
from lawsy.app.utils.history import Report
from lawsy.app.utils.mindmap import draw_mindmap
from lawsy.utils.logging import logger

REPORT_PAGES = {}


def get_logo_path() -> Path:
    return Path(__file__).parent / "Lawsy_logo_circle.png"


def get_logotitle_path() -> Path:
    return Path(__file__).parent / "Lawsy_logo_title_long_trans.png"


def create_report_page(report: Report):
    def page_func():
        dotenv.load_dotenv()
        css = (Path(__file__).parent / "styles" / "style.css").read_text()
        st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)

        # title logo
        logo_col, _ = st.columns([1, 5])
        with logo_col:
            st.image(get_logotitle_path())

        logo = get_logo_path()
        logger.info("reproduce previous report")
        if st.session_state.config_reasoning_details_display_enabled and report.messages is not None:
            with st.expander("Reasoning Details"):
                for message in report.messages:
                    role = message["role"]
                    content = message["content"]
                    if role == "user":
                        with st.chat_message(role):
                            st.write(content)
                    else:
                        with st.chat_message(role, avatar=logo):
                            st.write(content)
        pos = report.report_content.find("## ")
        assert pos >= 0
        title_and_lead = report.report_content[:pos]
        rest = report.report_content[pos:]
        title, lead = title_and_lead.split("\n", 1)
        # title
        st.write(title)
        st.write(lead)
        draw_mindmap(report.mindmap)
        tooltips = get_reference_tooltip_html(report.references)
        rest = embed_tooltips(rest, tooltips)
        st.write(rest, unsafe_allow_html=True)
        st.markdown("## References")
        for i, result in enumerate(report.references, start=1):
            html = get_hiddenbox_ref_html(i, result)
            st.markdown(html, unsafe_allow_html=True)
        st.markdown(
            """
            <style>
            .custom-text-warning {
                color: grey !important;
                font-size: 12px !important;
            }
            </style>
            """,
            unsafe_allow_html=True,
        )
        warning_text = (
            '<p class="custom-text-warning">'
            "※Lawsyの回答は必ずしも正しいとは限りません。重要な情報は確認するようにしてください。"
            "</p>"
        )
        st.markdown(warning_text, unsafe_allow_html=True)

        return

    return page_func
