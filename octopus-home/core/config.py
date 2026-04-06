from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Octopus Energy
    octopus_api_key: str = ""
    octopus_product_code: str = "AGILE-24-10-01"
    octopus_tariff_code: str = "E-1R-AGILE-24-10-01-A"
    price_cheap_threshold_pence: float = 15.0

    # Alexa
    alexa_client_id: str = ""
    alexa_client_secret: str = ""
    alexa_skill_id: str = ""

    # Google Home
    google_client_id: str = ""
    google_client_secret: str = ""
    google_service_account_json: str = "./google-service-account.json"
    google_agent_user_id: str = "homeuser1"

    # Auth
    jwt_secret: str = "change_me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 30

    # App
    base_url: str = "http://localhost:8000"
    database_url: str = "sqlite+aiosqlite:///./octopus_home.db"
    log_level: str = "INFO"


settings = Settings()
