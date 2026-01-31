from pydantic_settings import BaseSettings
from pydantic import Field

class Settings(BaseSettings):
    tg_token: str = Field(..., description="Telegram Bot Token")
    allowed_user_id: int = Field(..., description="Allowed Telegram User ID")
    cf_api_token: str = Field(..., description="Cloudflare API Token")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()
