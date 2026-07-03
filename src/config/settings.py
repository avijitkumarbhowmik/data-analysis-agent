from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="AGENT_",
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
    )

    database_url: str = Field(default="sqlite:///./data/agent.db")
    log_level: str = Field(default="INFO")

    # LLM provider — auto-detected from whichever key is set if left blank
    llm_provider: str = Field(default="")   # "anthropic" | "gemini"
    llm_model: str = Field(default="")      # uses provider default when blank

    # Provider keys — set exactly one
    anthropic_api_key: str = Field(default="")
    gemini_api_key: str = Field(default="")

    # Per-query cost rates (Phase 2). gemini-2.5-flash pricing, USD per 1k tokens.
    # Defaults: input ~$0.075 / 1M tokens, output ~$0.30 / 1M tokens.
    # Read from AGENT_GEMINI_INPUT_USD_PER_1K / AGENT_GEMINI_OUTPUT_USD_PER_1K.
    gemini_input_usd_per_1k: float = Field(default=0.000075)
    gemini_output_usd_per_1k: float = Field(default=0.0003)


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
