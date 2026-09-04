from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"), env_file_encoding="utf-8", extra="ignore"
    )

    app_name: str = "Prompt-Injection Tester"
    environment: str = "development"
    debug: bool = True
    secret_key: str = "change-me"
    log_level: str = "INFO"
    log_format: str = "json"

    database_url: str = "sqlite:///./prompt_inject.db"

    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    llm_provider: str = "none"  # none | mock | openai | groq
    llm_api_key: str = ""
    llm_base_url: str = ""
    judge_model: str = "gpt-4o-mini"
    attack_model: str = "gpt-4o-mini"
    embedding_provider: str = "none"  # none | sentence-transformers | openai
    embedding_model: str = "all-MiniLM-L6-v2"

    max_concurrency: int = 5
    request_timeout: int = 30
    max_attacks: int = 200
    default_rate_limit: int = 10
    attack_gen_timeout: int = 60
    attack_gen_max_retries: int = 2
    max_generated_attacks: int = 25
    max_response_length: int = 200000

    ssrf_block_private: bool = True
    ssrf_allow_localhost_dev: bool = True

    api_auth_enabled: bool = False
    api_username: str = "admin"
    api_password: str = "change-me"

    @property
    def cors_origin_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()