"""
Runtime configuration — pydantic-settings, env-driven, fail-fast on a
missing required variable (docs/architecture/03-backend-architecture.md
§13). Extended in Phase 6 Module 1 (Core Framework) with the full settings
surface every later module needs: JWT signing, CORS, Redis/Celery broker
URLs, and third-party service credentials. Every later module reads
settings from here rather than calling `os.environ` directly, so the
entire configuration surface is validated once, at process startup, and
is fully typed everywhere it's used.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- Application ---
    APP_NAME: str = "NurseryVerse AI API"
    APP_ENV: str = "development"  # development | staging | production
    APP_DEBUG: bool = False
    API_V1_PREFIX: str = "/api/v1"

    # --- Database ---
    POSTGRES_HOST: str = "postgres"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "nurseryverse"
    POSTGRES_USER: str = "nurseryverse"
    POSTGRES_PASSWORD: str = ""
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 10

    # --- Auth (Module 2) ---
    # RS256, not HS256: lets resource servers (e.g. a future separate
    # notifications worker) verify tokens with only the public key,
    # without holding a shared secret capable of also *signing* tokens.
    JWT_PRIVATE_KEY: str = ""
    JWT_PUBLIC_KEY: str = ""
    JWT_ALGORITHM: str = "RS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # --- Account lockout / brute-force protection (Module 2) ---
    AUTH_MAX_FAILED_LOGIN_ATTEMPTS: int = 5
    AUTH_LOCKOUT_DURATION_MINUTES: int = 15
    AUTH_EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS: int = 24
    AUTH_PASSWORD_RESET_TOKEN_EXPIRE_MINUTES: int = 60
    AUTH_LOGIN_RATE_LIMIT_PER_MINUTE: int = 10
    AUTH_PASSWORD_RESET_RATE_LIMIT_PER_HOUR: int = 5

    # --- Employee invitations (Module 4) ---
    AUTH_INVITE_EXPIRE_DAYS: int = 7
    AUTH_SIGNUP_RATE_LIMIT_PER_HOUR: int = 10

    # --- Plant Passport public tokens (Module 9) ---
    # Same fail-fast-in-production / ephemeral-in-dev resolution pattern as
    # JWT_PRIVATE_KEY (app/core/keys.py) -- see
    # app/services/passport_service.py's resolve_passport_token_secret.
    PASSPORT_TOKEN_SECRET: str = ""
    # 0 = tokens never expire by default; a caller may still request a
    # specific expiration per-passport (the module's own "support
    # expiration if configured" requirement -- configurable per call, with
    # this as the fallback when the caller doesn't specify one).
    PASSPORT_TOKEN_DEFAULT_EXPIRE_DAYS: int = 0

    # --- Refresh token cookie (optional; header-based bearer refresh is the
    # default/primary mode — see docs/architecture/18-module2-authentication.md
    # "Cookies vs. bearer tokens") ---
    AUTH_USE_REFRESH_COOKIE: bool = False
    AUTH_REFRESH_COOKIE_NAME: str = "nv_refresh_token"
    AUTH_REFRESH_COOKIE_SECURE: bool = True
    # Phase 6 Module 14 (Production Readiness) defect fix: was `str`.
    # Starlette's `Response.set_cookie(samesite=...)` (app/api/routes/
    # auth.py's `_set_auth_cookies`, the only caller) only accepts
    # `Literal["lax", "strict", "none"] | None` -- a plain `str` type here
    # let mypy see two call sites as "passing str where Literal expected"
    # (`mypy app` caught this while validating this module). Narrowing the
    # field type is also a genuine correctness improvement, not just a
    # type-checker appeasement: pydantic-settings validates the env var
    # against this Literal at startup, so a typo'd
    # `AUTH_REFRESH_COOKIE_SAMESITE=strictt` now fails fast at process
    # boot instead of silently reaching Starlette, which would have
    # raised its own, less obviously-connected error deep inside the
    # first login request that hit cookie mode.
    AUTH_REFRESH_COOKIE_SAMESITE: Literal["lax", "strict", "none"] = "strict"

    # --- Email delivery (Module 2 sends verification/reset emails directly;
    # Module 11 (Notifications) reuses this same real SMTP client as its
    # EmailProvider implementation, not a mock — needs real credentials
    # configured per-deployment to actually deliver mail) ---
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_USE_TLS: bool = True
    SMTP_FROM_EMAIL: str = "no-reply@nurseryverse.ai"
    SMTP_FROM_NAME: str = "NurseryVerse AI"
    FRONTEND_BASE_URL: str = "http://localhost:3000"

    # --- Module 11 (Notifications): SMS / Push provider credentials. No
    # SMS/push vendor was selected in Phases 1-4 (same "infrastructure/
    # credentials gap, not a code gap" situation SMTP_HOST documents above)
    # -- SmsProvider/PushProvider log-and-no-op when these are unset, exactly
    # like SmtpEmailSender does for SMTP_HOST. ---
    SMS_PROVIDER_API_KEY: str = ""
    SMS_PROVIDER_FROM_NUMBER: str = ""
    PUSH_PROVIDER_API_KEY: str = ""

    # --- CORS ---
    CORS_ALLOWED_ORIGINS: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])

    # --- Redis / Celery ---
    REDIS_URL: str = "redis://redis:6379/0"
    CELERY_BROKER_URL: str = "redis://redis:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://redis:6379/2"

    # --- Third-party services ---
    CLOUDINARY_CLOUD_NAME: str = ""
    CLOUDINARY_API_KEY: str = ""
    CLOUDINARY_API_SECRET: str = ""
    ANTHROPIC_API_KEY: str = ""
    VOYAGE_API_KEY: str = ""  # embeddings for the RAG knowledge base (app/models/ai.py)

    # --- Phase 6 Module 10 (AI Platform) ---
    # `ANTHROPIC_MODEL` is the AI Assistant's model id (docs/architecture/
    # 06-ai-architecture.md §1: "Anthropic Claude API, tool-calling").
    # `MODEL_ARTIFACT_BASE_PATH` is where `ModelRegistry` (app/ai/common/
    # model_registry.py) looks for trained weights for the six prediction
    # modules, per that same doc's §2/§10 ("weights are read from
    # Cloudinary-hosted (or equivalent object storage) artifacts at
    # `models/<capability>/<version>/`... not baked into the container
    # image"). Empty by default -- no capability has a trained artifact in
    # this environment, so `ModelRegistry.get()` raises the documented,
    # typed `ModelUnavailableError` for every capability until a real path
    # is configured; this is the designed graceful-degradation path
    # (docs/architecture/02-low-level-design.md's AI Predictions module
    # "Error handling" note), not a bug.
    ANTHROPIC_MODEL: str = "claude-sonnet-4-5-20250929"
    ASSISTANT_MAX_TOKENS: int = 1024
    ASSISTANT_MAX_TOOL_ITERATIONS: int = 5
    MODEL_ARTIFACT_BASE_PATH: str = ""

    # Cost tracking (FR-9's "token usage analytics"/"cost tracking" —
    # AssistantOrchestrator multiplies the Anthropic API response's own
    # `usage.input_tokens`/`usage.output_tokens` by these per-million-token
    # rates to populate `ai_assistant_messages.cost_usd` (migration 0015).
    # Defaults are Anthropic's published list price for the configured
    # `ANTHROPIC_MODEL` (Claude Sonnet) at the time this module was built;
    # deployments should override these two settings if pricing changes or
    # a different model is configured, rather than editing code.
    ANTHROPIC_INPUT_COST_PER_MTOK: float = 3.00
    ANTHROPIC_OUTPUT_COST_PER_MTOK: float = 15.00

    # --- Ollama (local LLM / embedding provider) ---
    # `LLM_PROVIDER` selects the backend for the AI Assistant's chat
    # completions: "anthropic" uses the Anthropic Claude API above;
    # "ollama" uses a local Ollama server. When set to "ollama", the
    # `ANTHROPIC_API_KEY` check in the orchestrator is bypassed and the
    # `OLLAMA_*` settings below are used instead.
    LLM_PROVIDER: str = "ollama"  # "anthropic" | "ollama"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_CHAT_MODEL: str = "llama3.2"

    # `EMBEDDING_PROVIDER` selects the backend for RAG knowledge-base
    # embeddings: "voyage" uses the Voyage AI API; "ollama" uses a local
    # Ollama server. Both mxbai-embed-large (Ollama) and voyage-3 (Voyage
    # AI) produce 1024-dimensional vectors matching `EMBEDDING_DIM` in
    # app/models/ai.py.
    EMBEDDING_PROVIDER: str = "ollama"  # "voyage" | "ollama"
    OLLAMA_EMBEDDING_MODEL: str = "mxbai-embed-large"

    # --- Phase 6 Module 12 (Reports & Analytics) ---
    # `app/reporting/file_storage.py`'s `LocalFileStorage` fallback path,
    # used whenever `CLOUDINARY_*` above is unset -- same disclosed
    # "no vendor credentials in this environment" gap `SMTP_HOST`/
    # `SMS_PROVIDER_API_KEY`/`PUSH_PROVIDER_API_KEY` already document,
    # except a generated report genuinely needs somewhere to live even
    # absent real Cloudinary credentials, so this is a working local-disk
    # substitute rather than a no-op.
    REPORTS_LOCAL_STORAGE_PATH: str = "var/reports"

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"

    @property
    def sqlalchemy_database_uri(self) -> str:
        return (
            f"postgresql+psycopg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def sqlalchemy_database_uri_async(self) -> str:
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )


@lru_cache
def get_settings() -> Settings:
    """
    Cached accessor — tests override this via FastAPI's dependency-override
    mechanism (see tests/conftest.py) rather than mutating the module-level
    singleton, so settings can vary per-test without cross-test leakage.
    """
    return Settings()


settings = get_settings()
