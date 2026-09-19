from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Database
    database_url: str = "postgresql://postgres:postgres@localhost:5432/marketintel"

    # JWT
    jwt_secret: str = "change_me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7

    # External services
    scraper_api_base_url: str = "http://localhost:8888"
    n8n_webhook_base_url: str = "http://localhost:5678"
    n8n_api_key: str = ""
    openrouter_api_key: str = ""
    # Public URL of this dashboard backend (used as webhook callback for n8n)
    dashboard_public_url: str = "http://localhost:8000"

    # CORS
    cors_origins: str = "http://localhost:3000"

    # Email / SMTP (Gmail)
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""          # your Gmail address
    smtp_password: str = ""      # Gmail App Password (16-char)
    smtp_from: str = ""          # defaults to smtp_user if empty
    smtp_enabled: bool = True    # set False in dev to skip sending

    # OTP
    otp_expire_minutes: int = 10

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",")]

    @property
    def smtp_from_address(self) -> str:
        return self.smtp_from or self.smtp_user


settings = Settings()
