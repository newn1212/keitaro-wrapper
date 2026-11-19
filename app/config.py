from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    keitaro_url: str = "https://tlk.host"
    keitaro_api_key: str = ""
    database_url: str = "sqlite:///./app.db"
    domain_name: str = "in.posdk.xyz"
    group_name: str = "FORTESTS"
    source_name: str = "FORTESTS"
    name_prefix: str = ""


settings = Settings()
