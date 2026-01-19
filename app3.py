import streamlit as st
from secdemo.state import init_session
from secdemo.ui import render_app

st.set_page_config(
    page_title="Security Demo (ZAP Live + Report + Quick Checks)",
    layout="wide",
)

init_session()
render_app()
