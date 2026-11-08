"""Runtime configuration, read from environment variables (and an optional .env file).

Author: Saamarth Attray
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

PROVIDER_DEFAULTS: dict[str, tuple[str, str]] = {
    # provider -> (base_url, default_model). Both speak the OpenAI chat-completions protocol.
    "groq": ("https://api.groq.com/openai/v1", "llama-3.3-70b-versatile"),
    "openai": ("https://api.openai.com/v1", "gpt-4o-mini"),
}


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    values: dict[str, str] = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")  # a repeated variable: the LAST line wins
    for key, value in values.items():
        os.environ.setdefault(key, value)  # real environment variables still take priority over the file


def _env(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(name)
    return value if value not in (None, "") else default


def _bool(name: str, default: bool) -> bool:
    value = _env(name)
    return default if value is None else value.strip().lower() in ("1", "true", "yes", "on")


def _float(name: str, default: float) -> float:
    value = _env(name)
    return default if value is None else float(value)


def _int(name: str, default: int) -> int:
    value = _env(name)
    return default if value is None else int(value)


def parse_demo_targets(raw: str | None) -> list[tuple[str, str]]:
    """`Name:+15551234567;Other Name:+15557654321` -> [(name, phone), ...]"""
    out: list[tuple[str, str]] = []
    for chunk in (raw or "").split(";"):
        chunk = chunk.strip()
        if not chunk or ":" not in chunk:
            continue
        name, phone = chunk.rsplit(":", 1)
        out.append((name.strip(), phone.strip()))
    return out


@dataclass(frozen=True)
class Settings:
    database_url: str = "sqlite+aiosqlite:///./swarmdial.db"
    redis_url: str | None = None
    public_base_url: str = ""
    cors_origins: tuple[str, ...] = ("http://localhost:3000", "http://127.0.0.1:3000")

    llm_provider: str = "none"  # none | groq | openai
    llm_api_key: str | None = None
    llm_model: str | None = None
    llm_base_url: str | None = None
    llm_fallback_model: str | None = None  # Groq default llama-3.1-8b-instant; used after repeated failures (rate limits)
    force_scripted_agents: bool = False  # use the offline scripted brain even if an LLM is configured

    twilio_account_sid: str | None = None
    twilio_auth_token: str | None = None
    twilio_from_number: str | None = None
    validate_twilio_signature: bool = True

    deepgram_api_key: str | None = None
    deepgram_stt_model: str = "nova-2-phonecall"
    deepgram_tts_voice: str = "aura-asteria-en"

    google_places_api_key: str | None = None
    default_lat: float = 37.7749
    default_lng: float = -122.4194

    allow_real_business_calls: bool = True  # default: real businesses near the user. Set false to dial only DEMO_TARGETS
    record_demo_calls: bool = False  # record calls to DEMO_TARGETS only (your own phones); never real businesses
    demo_targets: tuple[tuple[str, str], ...] = field(default_factory=tuple)

    max_targets: int = 10
    backup_targets: int = 6
    max_concurrent_calls: int = 12
    target_yes_count: int = 4
    call_timeout_s: float = 180.0
    dial_stagger_s: float = 1.1
    redial_cooldown_min: int = 30  # never phone the same business number twice within this window
    max_calls_per_day: int = 150  # safety cap on live calls per server day (0 = unlimited)
    sim_speed: float = 1.0

    @property
    def llm_enabled(self) -> bool:
        return self.llm_provider in PROVIDER_DEFAULTS and bool(self.llm_api_key)

    @property
    def resolved_llm_base_url(self) -> str:
        return self.llm_base_url or PROVIDER_DEFAULTS.get(self.llm_provider, ("", ""))[0]

    @property
    def resolved_llm_model(self) -> str:
        return self.llm_model or PROVIDER_DEFAULTS.get(self.llm_provider, ("", ""))[1]

    @property
    def twilio_enabled(self) -> bool:
        return bool(self.twilio_account_sid and self.twilio_auth_token and self.twilio_from_number)

    @property
    def deepgram_enabled(self) -> bool:
        return bool(self.deepgram_api_key)

    @property
    def places_enabled(self) -> bool:
        return bool(self.google_places_api_key)

    @property
    def ws_base_url(self) -> str:
        base = self.public_base_url.rstrip("/")
        if base.startswith("https://"):
            return "wss://" + base[len("https://"):]
        if base.startswith("http://"):
            return "ws://" + base[len("http://"):]
        return base

    def live_missing(self) -> list[str]:
        """What is still needed before live (real phone) mode can run."""
        missing = []
        if not self.twilio_enabled:
            missing.append("TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN / TWILIO_FROM_NUMBER")
        if not self.deepgram_enabled:
            missing.append("DEEPGRAM_API_KEY")
        if not self.llm_enabled:
            missing.append("GROQ_API_KEY or OPENAI_API_KEY")
        if not self.public_base_url:
            missing.append("PUBLIC_BASE_URL (public https URL, e.g. an ngrok tunnel)")
        if self.allow_real_business_calls and not self.places_enabled:
            missing.append("GOOGLE_PLACES_API_KEY (needed to find real businesses)")
        if not self.allow_real_business_calls and not self.demo_targets:
            missing.append("DEMO_TARGETS (test phone numbers) because ALLOW_REAL_BUSINESS_CALLS=false")
        return missing

def _default_fallback(provider: str, model: str | None) -> str:
    """Backup model for when the main one is rate limited. A capable one: the small 8B model fumbles tool calls and
    sounds stilted, which callers notice. Groq gives each model its own rate-limit allowance."""
    if provider != "groq":
        return ""
    main = model or PROVIDER_DEFAULTS["groq"][1]
    return "llama-3.1-8b-instant" if main == "llama-3.3-70b-versatile" else "llama-3.3-70b-versatile"

def load_settings() -> Settings:
    _load_dotenv(Path(__file__).resolve().parent.parent / ".env")

    provider = (_env("LLM_PROVIDER") or "").lower()
    api_key = _env("LLM_API_KEY")
    if not provider or provider == "auto":
        if _env("GROQ_API_KEY"):
            provider, api_key = "groq", api_key or _env("GROQ_API_KEY")
        elif _env("OPENAI_API_KEY"):
            provider, api_key = "openai", api_key or _env("OPENAI_API_KEY")
        else:
            provider = "none"
    elif api_key is None:
        api_key = _env("GROQ_API_KEY") if provider == "groq" else _env("OPENAI_API_KEY")

    origins = tuple(
        o.strip() for o in (_env("CORS_ORIGINS") or "http://localhost:3000,http://127.0.0.1:3000").split(",") if o.strip()
    )

    return Settings(
        database_url=_env("DATABASE_URL", "sqlite+aiosqlite:///./swarmdial.db") or "",
        redis_url=_env("REDIS_URL"),
        public_base_url=(_env("PUBLIC_BASE_URL") or "").rstrip("/"),
        cors_origins=origins,
        llm_provider=provider,
        llm_api_key=api_key,
        llm_model=_env("LLM_MODEL"),
        llm_base_url=_env("LLM_BASE_URL"),
        llm_fallback_model=(os.environ.get("LLM_FALLBACK_MODEL", _default_fallback(provider, _env("LLM_MODEL"))) or None),
        force_scripted_agents=_bool("FORCE_SCRIPTED_AGENTS", False),
        twilio_account_sid=_env("TWILIO_ACCOUNT_SID"),
        twilio_auth_token=_env("TWILIO_AUTH_TOKEN"),
        twilio_from_number=_env("TWILIO_FROM_NUMBER"),
        validate_twilio_signature=_bool("VALIDATE_TWILIO_SIGNATURE", True),
        deepgram_api_key=_env("DEEPGRAM_API_KEY"),
        deepgram_stt_model=_env("DEEPGRAM_STT_MODEL", "nova-2-phonecall") or "nova-2-phonecall",
        deepgram_tts_voice=_env("DEEPGRAM_TTS_VOICE", "aura-asteria-en") or "aura-asteria-en",
        google_places_api_key=_env("GOOGLE_PLACES_API_KEY"),
        default_lat=_float("DEFAULT_LAT", 37.7749),
        default_lng=_float("DEFAULT_LNG", -122.4194),
        allow_real_business_calls=_bool("ALLOW_REAL_BUSINESS_CALLS", True),
        record_demo_calls=_bool("RECORD_DEMO_CALLS", False),
        demo_targets=tuple(parse_demo_targets(_env("DEMO_TARGETS"))),
        max_targets=_int("MAX_TARGETS", 10),
        backup_targets=_int("BACKUP_TARGETS", 5),
        max_concurrent_calls=_int("MAX_CONCURRENT_CALLS", 10),
        target_yes_count=_int("TARGET_YES_COUNT", 4),
        call_timeout_s=_float("CALL_TIMEOUT_S", 180.0),
        dial_stagger_s=_float("DIAL_STAGGER_S", 1.1),
        redial_cooldown_min=_int("REDIAL_COOLDOWN_MIN", 30),
        max_calls_per_day=_int("MAX_CALLS_PER_DAY", 150),
        sim_speed=_float("SIM_SPEED", 1.0),
    )
