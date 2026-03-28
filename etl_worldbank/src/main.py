import logging
from src.config import Config
from src.extract import fetch_countries, fetch_indicator
from src.transform import transform_countries, transform_indicator
from src.load import engine, load_countries, load_indicators, load_facts

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    config = Config()
    
    # Step 1: Extract and transform countries
    raw_countries = fetch_countries()
    countries = transform_countries(raw_countries)
    
    # Step 2: Extract and transform indicators
    indicator_defs = [
        {"code": "NY.GDP.PCAP.KD", "name": "GDP per capita (constant 2015 US$)", "unit": "USD"},
        {"code": "SP.POP.TOTL", "name": "Population, total", "unit": "Persons"},
        {"code": "SH.XPD.CHEX.GD.ZS", "name": "Current health expenditure (% of GDP)", "unit": "% GDP"},
        {"code": "SE.XPD.TOTL.GD.ZS", "name": "Government expenditure on education, total (% of GDP)", "unit": "% GDP"},
    ]
    
    valid_iso2 = {c["iso2_code"] for c in countries}
    
    all_facts = []
    indicators_to_load = []
    for ind in indicator_defs:
        raw = fetch_indicator(ind["code"])
        transformed = transform_indicator(raw, ind["code"], valid_iso2)
        all_facts.extend(transformed)
        indicators_to_load.append({
            "indicator_code": ind["code"],
            "indicator_name": ind["name"],
            "unit": ind["unit"]
        })
    
    # Step 3: Load into database
    with engine.begin() as conn:
        load_countries(conn, countries)
        load_indicators(conn, indicators_to_load)
        load_facts(conn, all_facts)
    
    logger.info("ETL pipeline completed successfully.")

if __name__ == "__main__":
    main()