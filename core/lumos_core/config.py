from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "LumOS Core"
    version: str = "1.4.0"
    host: str = "127.0.0.1"
    port: int = 8765
    llm_base_url: str = "http://127.0.0.1:8080/v1"
    llm_model: str = ""
    llm_timeout_seconds: float = 30.0
    llm_api_key: str = ""

    model_config = SettingsConfigDict(env_prefix="LUMOS_", extra="ignore")


settings = Settings()
