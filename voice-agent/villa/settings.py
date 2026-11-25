"""Configuration from environment variables.

In Docker the values come from the repository's ``.env`` (compose ``env_file``) plus the service's
overrides (MCP and backend URLs on the compose network). Run locally with ``uv run``, the root
``.env`` is loaded and the URLs fall back to the ports docker-compose publishes on localhost.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

ON = ("1", "true", "yes", "on")


def _flag(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    return default if raw is None or raw.strip() == "" else raw.strip().lower() in ON


def _list(name: str, default: list[str]) -> list[str]:
    raw = os.getenv(name)
    if not raw:
        return default
    return [v.strip() for v in raw.split(",") if v.strip()]


@dataclass(frozen=True)
class Settings:
    agent_name: str = field(default_factory=lambda: os.getenv("VOICE_AGENT_NAME", "villa"))

    # Backend (transcripts, history)
    backend_url: str = field(default_factory=lambda: os.getenv("VOICE_BACKEND_URL", "http://localhost:8000"))
    agent_secret: str = field(default_factory=lambda: os.getenv("VOICE_AGENT_SECRET", ""))

    # MCP servers: the same ones the text agent uses (an empty value falls back to the local port)
    mcp_sources: tuple[tuple[str, str], ...] = field(
        default_factory=lambda: tuple(
            (src, url)
            for src, url in (
                ("villaops", os.getenv("MCP_SERVER_URL") or "http://localhost:8001/mcp"),
                ("booking", os.getenv("BOOKING_MCP_URL") or "http://localhost:8002/mcp"),
                ("airbnb", os.getenv("AIRBNB_MCP_URL") or "http://localhost:8003/mcp"),
                ("tripadvisor", os.getenv("TRIPADVISOR_MCP_URL") or "http://localhost:8004/mcp"),
            )
            if src not in _list("VOICE_DISABLED_SOURCES", [])
        )
    )
    exa_api_key: str = field(default_factory=lambda: os.getenv("EXA_API_KEY", ""))

    # LLM via OpenRouter; the backup is another vendor, the last resort runs on LiveKit Inference
    openrouter_api_key: str = field(default_factory=lambda: os.getenv("OPENROUTER_API_KEY", ""))
    default_model: str = field(default_factory=lambda: _list("VOICE_MODELS", ["anthropic/claude-haiku-5.5"])[0])
    backup_model: str = field(default_factory=lambda: os.getenv("VOICE_BACKUP_MODEL", "google/gemini-3.1-flash-lite"))
    inference_backup_model: str = field(
        default_factory=lambda: os.getenv("VOICE_INFERENCE_BACKUP_MODEL", "openai/gpt-4.1-mini")
    )
    llm_timeout_s: float = field(default_factory=lambda: float(os.getenv("VOICE_LLM_TIMEOUT_S", "15")))

    # Voice: ElevenLabs first, then the LiveKit Inference voices mini-kulu uses
    eleven_api_key: str = field(default_factory=lambda: os.getenv("ELEVEN_API_KEY", ""))
    eleven_model: str = field(default_factory=lambda: os.getenv("ELEVEN_MODEL", "eleven_flash_v2_5"))
    # "hanna": a warm English voice the user picked (2026-11-25); works with the free-tier key
    eleven_voice_id: str = field(default_factory=lambda: os.getenv("ELEVEN_VOICE_ID", "4boNr3nCeZU6Yd1VGPvY"))
    tts_timeout_s: float = field(default_factory=lambda: float(os.getenv("VOICE_TTS_TIMEOUT_S", "5")))

    noise_cancellation: bool = field(default_factory=lambda: _flag("VOICE_NOISE_CANCELLATION", True))
    thinking_sound: bool = field(default_factory=lambda: _flag("VOICE_THINKING_SOUND", True))
    tool_timeout_s: float = field(default_factory=lambda: float(os.getenv("VOICE_TOOL_TIMEOUT_S", "20")))
    max_web_searches: int = field(default_factory=lambda: int(os.getenv("VOICE_MAX_WEB_SEARCHES", "6")))


settings = Settings()
