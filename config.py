import os
from datetime import date
from dotenv import load_dotenv

load_dotenv()

PROPERTY_ID = os.environ.get("GA4_PROPERTY_ID", "properties/413595793")
SERVICE_ACCOUNT_JSON = os.environ.get("GA4_SERVICE_ACCOUNT_JSON", "")

DEFAULT_BEFORE_START = "2026-01-01"
DEFAULT_BEFORE_END   = "2026-06-03"
DEFAULT_AFTER_START  = "2026-06-04"
DEFAULT_AFTER_END    = str(date.today())
