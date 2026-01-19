import streamlit as st
from secdemo.ui import render_app

st.set_page_config(
    page_title="Security Demo (ZAP Live + Report + Quick Checks)",
    layout="wide",
)

render_app()
