from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://USER:PASSWORD@localhost:5432/contamination_cc"

    mqtt_broker_host: str = "localhost"
    mqtt_broker_port: int = 1883
    mqtt_username: str = ""
    mqtt_password: str = ""

    retention_hours: int = 12
    baselining_period_seconds: int = 90

    node_orchestrator_url: str = "http://localhost:8100"

    log_level: str = "INFO"

    registry_path: str = str(REPO_ROOT / "config" / "registry.json")

    # Where nodes download pushed model files from (§6: HTTP download, the closer analog to a
    # real OTA flow) -- this service's own externally-reachable base URL.
    public_url: str = "http://localhost:8000"
    model_files_dir: str = str(REPO_ROOT / "model_files")


@lru_cache
def get_settings() -> Settings:
    return Settings()
