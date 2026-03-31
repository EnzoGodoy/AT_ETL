import logging
from sqlalchemy import create_engine, MetaData, Table, Column, String, Text, Numeric, SmallInteger, TIMESTAMP, text
from sqlalchemy.dialects.postgresql import insert
from src.config import Config

logger = logging.getLogger(__name__)

config = Config()
engine = create_engine(config.db_url, echo=False)

metadata = MetaData()

# Define tables using Core
countries_table = Table(
    "countries", metadata,
    Column("iso2_code", String(2), primary_key=True),
    Column("iso3_code", String(3)),
    Column("name", String(100), nullable=False),
    Column("region", String(80)),
    Column("income_group", String(60)),
    Column("capital", String(80)),
    Column("longitude", Numeric(9,4)),
    Column("latitude", Numeric(9,4)),
    Column("loaded_at", TIMESTAMP, server_default=text("NOW()")),
)

indicators_table = Table(
    "indicators", metadata,
    Column("indicator_code", String(40), primary_key=True),
    Column("indicator_name", Text, nullable=False),
    Column("unit", String(30)),
)

wdi_facts_table = Table(
    "wdi_facts", metadata,
    Column("iso2_code", String(2), primary_key=True),
    Column("indicator_code", String(40), primary_key=True),
    Column("year", SmallInteger, primary_key=True),
    Column("value", Numeric(18,4)),
    Column("loaded_at", TIMESTAMP, server_default=text("NOW()")),
)

def load_countries(conn, countries_list):
    """Upsert countries using on_conflict_do_update."""
    if not countries_list:
        logger.warning("No countries to load; skipping upsert.")
        return

    stmt = insert(countries_table).values(countries_list)
    stmt = stmt.on_conflict_do_update(
        index_elements=["iso2_code"],
        set_={
            "iso3_code": stmt.excluded.iso3_code,
            "name": stmt.excluded.name,
            "region": stmt.excluded.region,
            "income_group": stmt.excluded.income_group,
            "capital": stmt.excluded.capital,
            "longitude": stmt.excluded.longitude,
            "latitude": stmt.excluded.latitude,
            "loaded_at": text("NOW()")
        }
    )
    conn.execute(stmt)
    logger.info(f"Loaded {len(countries_list)} countries (upsert).")

def load_indicators(conn, indicators_list):
    """Upsert indicators."""
    if not indicators_list:
        logger.warning("No indicators to load; skipping upsert.")
        return

    stmt = insert(indicators_table).values(indicators_list)
    stmt = stmt.on_conflict_do_update(
        index_elements=["indicator_code"],
        set_={
            "indicator_name": stmt.excluded.indicator_name,
            "unit": stmt.excluded.unit,
        }
    )
    conn.execute(stmt)
    logger.info(f"Loaded {len(indicators_list)} indicators (upsert).")

def load_facts(conn, facts_list):
    """Upsert wdi_facts."""
    if not facts_list:
        return
    stmt = insert(wdi_facts_table).values(facts_list)
    stmt = stmt.on_conflict_do_update(
        index_elements=["iso2_code", "indicator_code", "year"],
        set_={
            "value": stmt.excluded.value,
            "loaded_at": text("NOW()")
        }
    )
    conn.execute(stmt)
    logger.info(f"Loaded {len(facts_list)} facts (upsert).")