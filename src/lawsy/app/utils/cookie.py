import json
from typing import Any
from uuid import uuid4

import streamlit as st
from streamlit_cookies_controller import CookieController

cookie_controller = None


def init_cookies():
    global cookie_controller
    if "lawsy_cookie_initialized" not in st.session_state:
        st.session_state.lawsy_cookie_initialized = True
    cookie_controller = CookieController(key="lawsy-cookie")


def get_user_id() -> str:
    while not st.session_state.get("lawsy_cookie_initialized", False):
        init_cookies()
        st.session_state.lawsy_cookie_initialized = True
    assert cookie_controller is not None
    user_id = cookie_controller.get("user_id")
    if user_id is None:
        user_id = "user-" + str(uuid4())
    cookie_controller.set("user_id", user_id, max_age=365 * 86400)
    return user_id


def get_cookie(name: str) -> Any:
    assert cookie_controller is not None
    val = cookie_controller.get(name)
    if val is not None:
        val = json.loads(val)
    return val


def set_cookie(name: str, value: Any) -> None:
    assert cookie_controller is not None
    cookie_controller.set(name, json.dumps(value), max_age=365 * 86400)
