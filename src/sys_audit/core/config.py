"""Application configuration using pydantic-settings."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/sys_audit",
        description="PostgreSQL connection URL",
    )

    # LLM
    ollama_base_url: str = Field(
        default="http://localhost:11434",
        description="Ollama API base URL",
    )
    ollama_model: str = Field(
        default="qwen2.5-coder:7b",
        description="Default Ollama model for analysis",
    )
    ollama_timeout: int = Field(
        default=120,
        description="Timeout in seconds for LLM requests",
    )

    # Analysis
    complexity_threshold: int = Field(
        default=10,
        description="Cyclomatic complexity threshold for flagging",
    )
    cognitive_complexity_threshold: int = Field(
        default=15,
        description="Cognitive complexity threshold for flagging",
    )
    min_confidence: float = Field(
        default=0.6,
        description="Minimum confidence score to include findings",
    )

    # Paths
    prompts_dir: Path = Field(
        default=Path("prompts"),
        description="Directory containing prompt templates",
    )
    data_dir: Path = Field(
        default=Path.home() / ".sys-audit",
        description="Directory for local data storage",
    )

    # Server
    api_host: str = Field(default="127.0.0.1", description="API server host")
    api_port: int = Field(default=8080, description="API server port")


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
