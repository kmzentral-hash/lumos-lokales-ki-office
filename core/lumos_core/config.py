from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "LumOS Core"
    version: str = "0.3.0"
    host: str = "127.0.0.1"
    port: int = 8765

    model_config = SettingsConfigDict(env_prefix="LUMOS_", extra="ignore")


settings = Settings()
