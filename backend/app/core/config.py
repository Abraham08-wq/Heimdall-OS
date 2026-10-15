from typing import List, Union

from pydantic import AnyHttpUrl, AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "Cyber Intelligence Platform"
    API_V1_STR: str = "/api/v1"
    FRONTEND_URL: AnyHttpUrl = Field(...)

    # SECURITY
    JWT_SECRET_KEY: str = Field(validation_alias=AliasChoices("JWT_SECRET_KEY", "SECRET_KEY"))
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    ALGORITHM: str = "HS256"

    DEVELOPMENT_MODE: bool = False
    AUTH_BYPASS_ENABLED: bool = False
    ENABLE_GRAPH_DB: bool = True
    ENABLE_KAFKA: bool = True
    ENABLE_FIREWALL: bool = True
    ENABLE_OLLAMA: bool = True

    # Canonical default org used as fallback for users with no tenant linked.
    # A deterministic UUID so it never changes across restarts/seeds.
    DEFAULT_ORG_ID: str = "00000000-0000-0000-0000-000000000001"
    # CORS
    BACKEND_CORS_ORIGINS: List[AnyHttpUrl] = []

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)

    # POSTGRES
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = ""
    POSTGRES_DB: str = "cyberintel"
    DATABASE_URL: str = Field(...)

    # NEO4J — optional when ENABLE_GRAPH_DB=false
    NEO4J_URI: str = Field(default="bolt://neo4j:7687")
    NEO4J_USER: str = Field(default="neo4j")
    NEO4J_PASSWORD: str = Field(default="")

    # REDIS CACHE
    REDIS_URL: str = "redis://localhost:6379/0"

    # OSINT API KEYS
    SHODAN_API_KEY: str | None = None
    CENSYS_API_ID: str | None = None
    CENSYS_API_SECRET: str | None = None
    INTEL_X_API_KEY: str | None = None
    ALIENVAULT_API_KEY: str | None = None
    LEAK_LOOKUP_API_KEY: str | None = None

    # IMMUTABLE LEDGER (WORM) — signing key for worm_ledger.py's
    # WormLedgerService. Generate via pqc_engine.generate_lattice_keypair()
    # and store the PRIVATE key PEM here. The matching public key is kept
    # separately for verification purposes, not needed by the signing
    # service itself, but useful if anything later checks a signature.
    LEDGER_SIGNING_PRIVATE_KEY_PEM: str | None = None
    LEDGER_VERIFICATION_PUBLIC_KEY_PEM: str | None = None

    model_config = SettingsConfigDict(
        case_sensitive=True,
        # Primary env file is .env.local (project standard).
        # .env is kept as a fallback so CI/CD environments that ship only .env still work.
        env_file=(".env.local", ".env"),
        extra="ignore",
    )

    @field_validator(
        "DATABASE_URL",
        "JWT_SECRET_KEY",
        "FRONTEND_URL",
        mode="before",
    )
    @classmethod
    def validate_required_env(cls, value: str):
        if value is None or not str(value).strip():
            raise ValueError("must be provided via environment")
        return str(value).strip()

    @field_validator("JWT_SECRET_KEY")
    @classmethod
    def validate_jwt_secret_length(cls, value: str) -> str:
        if len(value) < 32:
            raise ValueError("JWT_SECRET_KEY must be at least 32 characters long")
        return value

    @property
    def SECRET_KEY(self) -> str:
        return self.JWT_SECRET_KEY

    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        return self.DATABASE_URL


settings = Settings()