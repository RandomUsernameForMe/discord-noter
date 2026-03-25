from dataclasses import dataclass
from dotenv import load_dotenv
import os

load_dotenv()


@dataclass
class Settings:
    discord_token: str
    anthropic_api_key: str
    google_service_account_json: str
    whisper_model: str
    notes_output_dir: str


def load_settings() -> Settings:
    return Settings(
        discord_token=os.environ["DISCORD_TOKEN"],
        anthropic_api_key=os.environ["ANTHROPIC_API_KEY"],
        google_service_account_json=os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "./service_account.json"),
        whisper_model=os.environ.get("WHISPER_MODEL", "large-v3"),
        notes_output_dir=os.environ.get("NOTES_OUTPUT_DIR", "./notes"),
    )
