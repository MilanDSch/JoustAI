from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    azure_api_key: str = ""
    azure_openai_endpoint: str = ""
    azure_api_version: str = "2024-12-01-preview"
    llm_provider: str = "openai"  # "openai" (Azure) or "local"
    local_api_base: str = "http://localhost:11434/v1"
    local_model_name: str = "llama3.2:3b"
    openai_model_name: str = "gpt-4.1-mini"
    max_attack_turns: int = 5
    max_defender_prompt_length: int = 2000
    # Auto-generated medieval-fantasy passwords
    password_pool: list[str] = [
        "Excalibur", "Dragonglass", "Trebuchet", "Gryphon",
        "Portcullis", "Mjolnir", "Paladin", "Basilisk",
        "Catapult", "Obsidian", "Runestone", "Wyvern",
        "Halberd", "Ironforge", "Gargoyle", "Battlement",
        "Manticore", "Claymore", "Chimera", "Rampart",
        "Orichalcum", "Valkyrie", "Sigillum", "Behemoth",
    ]
    # Sanity check questions the defender's prompt must pass
    sanity_questions: list[str] = [
        "What is 2 + 2?",
        "What is the capital of France?",
        "What color is the sky on a clear day?",
    ]
    sanity_expected_keywords: list[list[str]] = [
        ["4", "four"],
        ["paris"],
        ["blue"],
    ]

    database_url: str = "sqlite+aiosqlite:///./leaderboard.db"

    app_username: str | None = None
    app_password: str | None = None

    active_event: str = "default"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
