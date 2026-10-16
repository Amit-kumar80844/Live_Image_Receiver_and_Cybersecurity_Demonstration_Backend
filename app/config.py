from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_name: str = "Authorized Image Receiver"
    database_url: str = "sqlite:///./data/images.db"
    upload_dir: Path = Path("uploads")
    admin_token: str = "change-this-admin-token"
    max_upload_bytes: int = 10 * 1024 * 1024
    max_image_width: int = 12000
    max_image_height: int = 12000
    local_network_only: bool = False
    allowed_origins: str = "http://127.0.0.1:8000,http://localhost:8000"
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")
    @property
    def origins(self): return [x.strip() for x in self.allowed_origins.split(",") if x.strip()]

settings = Settings()
