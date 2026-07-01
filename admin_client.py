import streamlit as st
from google.analytics.admin import AnalyticsAdminServiceClient
import config


@st.cache_resource
def get_admin_client() -> AnalyticsAdminServiceClient:
    creds = config.get_credentials()
    if creds:
        return AnalyticsAdminServiceClient(credentials=creds)
    return AnalyticsAdminServiceClient()


@st.cache_data(ttl=3600, show_spinner=False)
def get_property_info() -> dict:
    client = get_admin_client()
    prop = client.get_property(name=config.PROPERTY_ID)
    return {
        "display_name": prop.display_name,
        "currency_code": prop.currency_code,
        "time_zone": prop.time_zone,
        "industry_category": str(prop.industry_category).split(".")[-1],
    }


@st.cache_data(ttl=3600, show_spinner=False)
def get_data_retention() -> dict:
    client = get_admin_client()
    settings = client.get_data_retention_settings(
        name=f"{config.PROPERTY_ID}/dataRetentionSettings"
    )
    return {
        "event_data_retention": str(settings.event_data_retention).split(".")[-1],
        "reset_user_data_on_new_activity": settings.reset_user_data_on_new_activity,
    }


@st.cache_data(ttl=3600, show_spinner=False)
def list_google_ads_links() -> list:
    client = get_admin_client()
    links = client.list_google_ads_links(parent=config.PROPERTY_ID)
    return [
        {
            "customer_id": link.customer_id,
            "ads_personalization_enabled": link.ads_personalization_enabled,
            "create_time": str(link.create_time)[:10] if link.create_time else "—",
        }
        for link in links
    ]


@st.cache_data(ttl=3600, show_spinner=False)
def list_audiences() -> list:
    client = get_admin_client()
    audiences = client.list_audiences(parent=config.PROPERTY_ID)
    return [
        {
            "display_name": a.display_name,
            "description": a.description,
            "membership_duration_days": a.membership_duration_days,
        }
        for a in audiences
    ]


@st.cache_data(ttl=3600, show_spinner=False)
def list_custom_dimensions() -> list:
    client = get_admin_client()
    dims = client.list_custom_dimensions(parent=config.PROPERTY_ID)
    return [
        {
            "display_name": d.display_name,
            "parameter_name": d.parameter_name,
            "scope": str(d.scope).split(".")[-1],
            "description": d.description,
        }
        for d in dims
    ]


@st.cache_data(ttl=3600, show_spinner=False)
def list_custom_metrics() -> list:
    client = get_admin_client()
    metrics = client.list_custom_metrics(parent=config.PROPERTY_ID)
    return [
        {
            "display_name": m.display_name,
            "parameter_name": m.parameter_name,
            "scope": str(m.scope).split(".")[-1],
            "measurement_unit": str(m.measurement_unit).split(".")[-1],
        }
        for m in metrics
    ]
