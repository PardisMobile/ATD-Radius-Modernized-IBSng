from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "ATD Radius"
    environment: str = "development"
    database_url: str = "postgresql://atd:atd@127.0.0.1:5432/atd_radius"
    api_prefix: str = "/api/v1"
    xmlrpc_enabled: bool = True
    radius_auth_host: str = "0.0.0.0"
    radius_auth_port: int = 1812
    radius_acct_host: str = "0.0.0.0"
    radius_acct_port: int = 1813

    model_config = SettingsConfigDict(env_file=".env", env_prefix="ATD_", extra="ignore")


settings = Settings()
