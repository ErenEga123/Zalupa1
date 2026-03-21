from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    bot_token: str
    bot_api_token: str = ""
    backend_base_url: str = "http://backend:8000"


settings = Settings()
