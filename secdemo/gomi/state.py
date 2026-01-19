import streamlit as st

# ここは「あなたの環境で確実に存在するモデル名」にしてOK
DEFAULT_MODEL_FALLBACK = "gemma2:9b-instruct-q5_K_M"


def init_session():
    """UIからも使える “状態の初期化” だけを担当（UIはimportしない）"""
    defaults = {
        "selected_model": DEFAULT_MODEL_FALLBACK,
        "temperature": 0.2,

        "zap_base": "http://127.0.0.1:8080",
        "zap_apikey": "",
        "zap_connected": False,
        "zap_version": "",
        "zap_mode": "",
        "zap_sites": [],
        "zap_history_rows": [],
        "zap_selected_msgid": "",
        "zap_selected_message": None,
        "zap_repeater_request": "",
        "zap_repeater_response": "",
        "zap_alerts_cache": None,

        "auto_refresh_on": False,
        "auto_refresh_secs": 5,
        "auto_refresh_scope": {"sites": True, "history": False, "alerts": False},
        "auto_history_start": 0,
        "auto_history_count": 50,
        "auto_history_url_regex": "",

        "generated_md": "",
        "edited_md": "",

        "intruder_results": [],

        "ui_show_browser_tab": False,
        "ui_global_alerts_bar": True,

        "alerts_last_count": 0,
        "alerts_last_high_plus": 0,
        "alerts_notif_on": True,
        "alerts_prev_sig_set": set(),
        "alerts_last_new": [],

        "alerts_url_regex": "",

        "ai_chat": [],
        "ai_last_hint": "",

        "last_updated_at": "",
        "last_updated_detail": "",

        "_main_tab": "🛰 ZAP Live",
        "_zap_tab": "🔌 Connect",
    }

    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v
