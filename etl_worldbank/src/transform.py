import logging
from datetime import datetime

logger = logging.getLogger(__name__)

def transform_countries(raw_countries):
    """
    Apply transformations to country data:
    - T1: Filter real countries (iso2 length 2) and income groups LIC/MIC/HIC
    - T2: Strip strings, replace empty with None, title-case region
    - T3: Convert latitude/longitude to float
    """
    cleaned = []
    current_year = datetime.now().year
    
    for c in raw_countries:
        # T1: real country filter
        iso2 = (c.get("iso2Code") or "").strip()
        if len(iso2) != 2:
            continue

        # Income group filter: normalize lower/upper middle income to MIC
        income_raw = (c.get("incomeLevel", {}).get("id") or "").strip()
        income_group = {
            "LIC": "LIC",
            "LMC": "MIC",
            "UMC": "MIC",
            "MIC": "MIC",
            "HIC": "HIC",
        }.get(income_raw)
        if not income_group:
            continue
        
        # T2: strip strings, replace empty with None
        name = c.get("name", "").strip() or None
        iso3 = c.get("iso3Code", "").strip() or None
        region_raw = c.get("region", {}).get("value", "").strip()
        region = region_raw.title() if region_raw else None
        capital = c.get("capitalCity", "").strip() or None
        # T3: convert lat/lon to float, handle missing
        try:
            lat = float(c.get("latitude", "")) if c.get("latitude") else None
        except (ValueError, TypeError):
            lat = None
        try:
            lon = float(c.get("longitude", "")) if c.get("longitude") else None
        except (ValueError, TypeError):
            lon = None
        
        cleaned.append({
            "iso2_code": iso2,
            "iso3_code": iso3,
            "name": name,
            "region": region,
            "income_group": income_group,
            "capital": capital,
            "latitude": lat,
            "longitude": lon,
        })
    logger.info(f"Transformed {len(cleaned)} countries after filtering.")
    return cleaned

def transform_indicator(raw_records, indicator_code, valid_iso2_set):
    """
    Transform indicator records:
    - T1: Filter records where country iso2 is in valid_iso2_set
    - T2: Strip strings (though not many string fields)
    - T3: Convert year to int, value to float (None if invalid)
    - T4: Filter years 2010-current
    """
    cleaned = []
    current_year = datetime.now().year
    for rec in raw_records:
        # T1: filter real country
        country_id = rec.get("country", {}).get("id", "")
        if country_id not in valid_iso2_set:
            continue
        
        # T3: convert year
        year_str = rec.get("date", "")
        try:
            year = int(year_str)
        except (ValueError, TypeError):
            continue  # skip if year invalid
        
        # T4: filter year
        if year < 2010 or year > current_year:
            continue
        
        # T3: convert value to float or None
        value = rec.get("value")
        if value is not None:
            try:
                value = float(value)
            except (ValueError, TypeError):
                value = None
        
        cleaned.append({
            "iso2_code": country_id,
            "indicator_code": indicator_code,
            "year": year,
            "value": value,
        })
    logger.info(f"Transformed {len(cleaned)} records for {indicator_code} after filtering.")
    return cleaned