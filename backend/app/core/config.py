from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/hose_quant"
    vnstock_source: str = "VCI"
    cors_origins: list[str] = ["http://localhost:3000"]

    # Strategy parameters (Section 4-5 of the spec)
    min_interest_coverage: float = 3.0
    sell_percentile_floor: float = 30.0
    sell_percentile_quarters: int = 2
    atr_stop_multiple: float = 2.5
    price_band_pct: float = 0.07
    lot_size: int = 100
    settlement_t_plus_days: int = 2


@lru_cache
def get_settings() -> Settings:
    return Settings()
