from pydantic_settings import BaseSettings
from pydantic import Field

class Settings(BaseSettings):
    # Databricks
    databricks_host: str = Field(..., env="DATABRICKS_HOST")           # https://adb-xxx.azuredatabricks.net
    databricks_token: str = Field(..., env="DATABRICKS_TOKEN")
    databricks_warehouse_id: str = Field(..., env="DATABRICKS_WAREHOUSE_ID")

    # Targets
    target_db: str = Field(default="sw_gold")
    target_table_earnings: str = Field(default="earnings_calendar")

    # Local I/O
    tmp_dir: str = Field(default="tmp")

    # Fetch knobs
    months_back: int = Field(default=12)

    class Config:
        env_file = ".env"
        case_sensitive = False

settings = Settings()
