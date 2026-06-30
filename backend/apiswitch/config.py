from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="APISWITCH_", env_file=".env", extra="ignore")

    app_name: str = "APISwitch"
    listen_host: str = "127.0.0.1"
    port: int = 8080
    database_url: str = "sqlite:///./apiswitch.db"
    auth_enabled: bool = False
    reload: bool = False
    stream_failure_mode: str = Field(default="strict_compat_mode")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
