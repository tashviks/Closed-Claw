"""
Application configuration — loaded from env / local storage
"""
import os
from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    debug: bool = os.getenv("DEBUG", "false").lower() == "true"
    data_dir: str = os.path.join(os.path.expanduser("~"), ".openclaw")
    max_tool_execution_time: int = 30  # seconds
    max_web_search_results: int = 10
    sandbox_enabled: bool = True

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
