from typing import Any

import streamlit as st
from streamlit_tags import st_tags

from lawsy.app.utils.cookie import get_cookie, set_cookie


def get_config(name: str, default_value: Any = None) -> Any:
    value = st.session_state.get("config_" + name)
    if value is None:
        value = get_cookie("config_" + name)
        if value is not None:
            st.session_state["config_" + name] = value
        else:
            value = default_value
    return value


def set_config(name: str, value: Any) -> None:
    st.session_state["config_" + name] = value
    set_cookie(name, value)


@st.dialog("すべての設定のリセット")
def reset_all_configs() -> None:
    st.write("すべての設定をリセットしますか？")
    _, col1, col2 = st.columns([6, 2, 2])
    with col1:
        ok = st.button("OK", use_container_width=True)
    with col2:
        cancel = st.button("Cancel", use_container_width=True)
    if cancel:
        st.rerun()
    if not ok:
        return
    for key in st.session_state.keys():
        assert isinstance(key, str)  # to avoid lint error
        if not key.startswith("config_"):
            continue
        st.session_state[key] = None
        set_cookie(key, None)
    st.rerun()


def init_config():
    def _init(name: str, default_value: Any) -> None:
        value = get_config(name)
        if value is None:
            value = default_value
        set_config(name, value)

    _init("free_web_search_enabled", True)
    _init("web_search_domains", ["go.jp", "courts.go.jp", "shugiin.go.jp", "sangiin.go.jp", "cao.go.jp"])
    _init("reasoning_details_display_enabled", False)


def create_config_page():
    # ------------
    # Web検索の設定
    # ------------
    st.subheader("Web Search")

    # ドメイン指定なしのWeb検索の有効化
    name = "free_web_search_enabled"
    value = get_config(name, True)
    free_web_search_enabled = st.checkbox("ドメイン指定なしのWeb検索を有効にする", value=value)
    if value != free_web_search_enabled:
        set_config(name, free_web_search_enabled)
        st.rerun()

    # ドメイン指定の検索において指定するドメイン
    name = "web_search_domains"
    values = get_config(name, ["go.jp", "courts.go.jp", "shugiin.go.jp", "sangiin.go.jp", "cao.go.jp"])
    web_search_domains = st_tags(value=values[:], label="ドメインを限定したWeb検索において参照可能なドメイン一覧")
    if values != web_search_domains:
        set_config(name, web_search_domains)
        st.rerun()

    # -------
    # 表示設定
    # -------
    st.subheader("History")

    # レポート表示時に推論過程を表示する
    name = "reasoning_details_display_enabled"
    value = get_config(name, False)
    reasoning_details_display_enabled = st.checkbox("過去のレポートを表示する際に推論過程も表示する", value=value)
    if value != reasoning_details_display_enabled:
        set_config(name, reasoning_details_display_enabled)
        st.rerun()

    # -------
    # リセット
    # -------
    st.subheader("リセット")
    if st.button("デフォルト設定に戻す", key="reset_all_configs_button"):
        reset_all_configs()
