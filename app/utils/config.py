# app/utils/config.py

import os
from functools import lru_cache
from typing import List, Optional
from pydantic import BaseModel, HttpUrl, Field, ConfigDict
from pydantic_settings import BaseSettings, SettingsConfigDict

class BrowserConfig(BaseModel):
    """Settings for the Playwright browser."""
    headless: bool = True
    viewport_width: int = 1920
    viewport_height: int = 1080
    timeout: int = 5000  # milliseconds
    screenshot_dir: str = "screenshots"
    trace_dir: str = "traces"

class AbacusConfig(BaseModel):
    """Abacus.AI specific configuration."""
    api_key: str = Field(alias="abacus_api_key")
    base_url: HttpUrl = Field(default="https://api.abacus.ai", alias="abacus_base_url")
    deployment_id: str = Field(alias="abacus_deployment_id")
    deployment_token: str = Field(alias="abacus_deployment_token")

    model_config = ConfigDict(
        populate_by_name=True,  # Allows population by alias
        from_attributes=True    # Allows creation from ORM objects
    )

def get_ia_api_key() -> List[str]:
    # Try GROK_API_KEY first, then GEMINI_API_KEY
    api_key = os.getenv("GROK_API_KEY") or os.getenv("GEMINI_API_KEY") or ""
    return [api_key]

class Settings(BaseSettings):
    """Main application settings."""
    # Basic app settings
    app_name: str = "WebTestAutomation"
    admin_email: str = "admin@example.com"  # Default value
    items_per_user: int = 50
    base_url: HttpUrl = "http://localhost:8000"
    runner_type: str = "default"
    #valid_api_keys: List[str] = Field(default_factory=get_ia_api_key)

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

    # New style configuration using SettingsConfigDict
    model_config = SettingsConfigDict(
        env_file=".env",
        env_nested_delimiter='__',
        case_sensitive=False,
        extra='allow',  # Allows extra fields in the settings
        validate_default=True  # Validates default values
    )

@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance.
    Returns:
        Settings: Application settings instance
    """
    return Settings()

def get_abacus_config() -> AbacusConfig:
    """
    Get Abacus.AI specific configuration.
    Returns:
        AbacusConfig: Abacus.AI configuration instance
    """
    settings = get_settings()
    return AbacusConfig(
        api_key=settings.abacus_api_key,
        base_url=settings.abacus_base_url,
        deployment_id=settings.abacus_deployment_id,
        deployment_token=settings.abacus_deployment_token
    )

HTML_SUMMARIZER_CONFIG = {
    'role_map': {
        'a': 'link',
        'button': 'button',
        'input': 'textbox',  # Default, overridden by input_type_map
        'select': 'combobox',
        'textarea': 'textbox',
        'h1': 'heading',
        'h2': 'heading',
        'h3': 'heading',
        'h4': 'heading',
        'h5': 'heading',
        'h6': 'heading',
        'div': 'generic',
        'span': 'generic',
        'p': 'text',
        'nav': 'navigation',
        'form': 'form',
        'header': 'banner',
        'footer': 'contentinfo',
        'main': 'main',
        'article': 'article',
        'section': 'region',
        'aside': 'complementary',
        'img': 'img',
        'svg': 'img',
        'iframe': 'document',
        'canvas': 'img',
    },
    'input_type_map': {
        'text': 'textbox',
        'search': 'searchbox',
        'email': 'textbox',
        'password': 'textbox',
        'checkbox': 'checkbox',
        'radio': 'radio',
        'submit': 'button',
        'reset': 'button',
        'file': 'textbox',
        'hidden': None,
        'image': 'button',
    },
    'visible_attributes': [
        'id', 'class', 'href', 'aria-label', 'data-testid', 'role', 'type',
        'value', 'alt', 'title', 'aria-selected', 'aria-checked',
        'aria-expanded', 'aria-controls', 'aria-describedby', 'aria-required',
        'tabindex', 'style', 'src', 'aria-level', 'name', 'placeholder'
    ]
}