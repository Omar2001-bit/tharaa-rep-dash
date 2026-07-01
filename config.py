import os
from datetime import date
from dotenv import load_dotenv
import streamlit as st
from google.oauth2 import service_account

load_dotenv()

PROPERTY_ID = os.environ.get("GA4_PROPERTY_ID", "properties/413595793")
SERVICE_ACCOUNT_JSON = os.environ.get("GA4_SERVICE_ACCOUNT_JSON", "")

DEFAULT_BEFORE_START = "2026-01-01"
DEFAULT_BEFORE_END   = "2026-06-03"
DEFAULT_AFTER_START  = "2026-06-04"
DEFAULT_AFTER_END    = str(date.today())

_SCOPES = ["https://www.googleapis.com/auth/analytics.readonly"]


def get_credentials():
    """Streamlit Cloud secrets (deployed) first, then a local service-account file (dev). None = fall back to ADC."""
    try:
        if "gcp_service_account" in st.secrets:
            return service_account.Credentials.from_service_account_info(
                dict(st.secrets["gcp_service_account"]), scopes=_SCOPES,
            )
    except Exception:
        pass
    if SERVICE_ACCOUNT_JSON and os.path.exists(SERVICE_ACCOUNT_JSON):
        return service_account.Credentials.from_service_account_file(
            SERVICE_ACCOUNT_JSON, scopes=_SCOPES,
        )
    return None
