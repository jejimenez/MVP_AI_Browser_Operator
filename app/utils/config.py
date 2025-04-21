# app/utils/config.py

from functools import lru_cache
from typing import List, Optional
from pydantic import BaseModel, HttpUrl, Field
from pydantic_settings import BaseSettings

class BrowserConfig(BaseModel):
    """Settings for the Playwright browser."""
    headless: bool = True
    viewport_width: int = 1920
    viewport_height: int = 1080
    timeout: int = 30000  # milliseconds
    screenshot_dir: str = "screenshots"
    trace_dir: str = "traces"

class AbacusConfig(BaseModel):
    """Abacus.AI specific configuration."""
    api_key: str = Field(alias="abacus_api_key")
    base_url: HttpUrl = Field(default="https://api.abacus.ai", alias="abacus_base_url")
    deployment_id: str = Field(alias="abacus_deployment_id")
    deployment_token: str = Field(alias="abacus_deployment_token")

class Settings(BaseSettings):
    """Main application settings."""
    # Basic app settings
    app_name: str = "WebTestAutomation"
    admin_email: str = "admin@example.com"  # Default value
    items_per_user: int = 50
    base_url: HttpUrl = "http://localhost:8000"
    runner_type: str = "default"
    valid_api_keys: List[str] = []

    # Browser configuration
    browser_config: BrowserConfig = BrowserConfig()

    # Abacus.AI settings
    abacus_api_key: str
    abacus_base_url: HttpUrl = "https://api.abacus.ai"
    abacus_deployment_id: str
    abacus_deployment_token: str

    # Application specific settings
    usr: str
    pw: str
    secret: str
    url: HttpUrl
    special_div: str

    class Config:
        env_file = ".env"
        env_nested_delimiter = '__'
        case_sensitive = False

@lru_cache()
def get_settings() -> Settings:
    """Cached settings instance."""
    return Settings()

# Optional: Helper function to get Abacus config
def get_abacus_config() -> AbacusConfig:
    """Get Abacus.AI specific configuration."""
    settings = get_settings()
    return AbacusConfig(
        api_key=settings.abacus_api_key,
        base_url=settings.abacus_base_url,
        deployment_id=settings.abacus_deployment_id,
        deployment_token=settings.abacus_deployment_token
    )