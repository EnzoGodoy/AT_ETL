import requests
import logging
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from src.config import Config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

config = Config()

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10),
       retry=retry_if_exception_type(requests.RequestException))
def fetch_json(url, params=None):
    """Fetch JSON from API with retry."""
    resp = requests.get(url, params=params)
    resp.raise_for_status()
    return resp.json()

def fetch_countries():
    """Fetch all countries from World Bank API."""
    url = f"{config.API_BASE_URL}/country"
    params = {"format": "json", "per_page": 300}
    logger.info("Fetching countries...")
    data = fetch_json(url, params)
    if not data or len(data) < 2:
        return []
    countries = data[1]
    logger.info(f"Fetched {len(countries)} country records.")
    return countries

def fetch_indicator(indicator_code):
    """Fetch all pages of indicator data for all countries."""
    base_url = f"{config.API_BASE_URL}/country/all/indicator/{indicator_code}"
    params = {"format": "json", "per_page": 1000}
    all_records = []
    page = 1
    while True:
        params["page"] = page
        logger.info(f"Fetching {indicator_code} page {page}...")
        data = fetch_json(base_url, params)
        if not data or len(data) < 2:
            break
        meta = data[0]
        records = data[1]
        if not records:
            break
        all_records.extend(records)
        total_pages = meta.get("pages", 1)
        if page >= total_pages:
            break
        page += 1
    logger.info(f"Fetched {len(all_records)} records for {indicator_code}.")
    return all_records