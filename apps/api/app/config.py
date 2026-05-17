from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "AgentNet API"
    environment: str = Field(default="development", alias="AGENTNET_ENV")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    database_url: str = Field(
        default="postgresql+asyncpg://agentnet:agentnet@localhost:5432/agentnet",
        alias="DATABASE_URL",
    )
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")
    max_payload_bytes: int = Field(default=1_048_576, alias="MAX_PAYLOAD_BYTES")
    ws_heartbeat_interval_s: int = Field(default=15, alias="WS_HEARTBEAT_INTERVAL_S")
    ws_heartbeat_timeout_s: int = Field(default=45, alias="WS_HEARTBEAT_TIMEOUT_S")
    ws_max_connections_per_agent: int = Field(default=3, alias="WS_MAX_CONNECTIONS_PER_AGENT")
    db_pool_pre_ping: bool = Field(default=False, alias="DB_POOL_PRE_PING")
    db_null_pool: bool = Field(default=False, alias="DB_NULL_POOL",
        description="Use NullPool instead of QueuePool (for tests)")

    # Phase 10: Rate limiting
    rate_limit_window_s: float = Field(
        default=60.0, alias="RATE_LIMIT_WINDOW_S",
        description="Sliding window duration in seconds for rate limit counters"
    )
    rate_limit_global_max: int = Field(
        default=1000, alias="RATE_LIMIT_GLOBAL_MAX",
        description="Max requests per window across all clients"
    )
    rate_limit_user_max: int = Field(
        default=300, alias="RATE_LIMIT_USER_MAX",
        description="Max requests per window per user"
    )
    rate_limit_agent_max: int = Field(
        default=200, alias="RATE_LIMIT_AGENT_MAX",
        description="Max requests per window per agent"
    )
    rate_limit_ip_max: int = Field(
        default=100, alias="RATE_LIMIT_IP_MAX",
        description="Max requests per window per IP address"
    )

    # Phase 10: Task timeout
    task_max_runtime_s: int = Field(
        default=600, alias="TASK_MAX_RUNTIME_S",
        description="Maximum task runtime in seconds before timeout expiry"
    )
    task_lease_duration_s: int = Field(
        default=60, alias="TASK_LEASE_DURATION_S",
        description="Lease duration in seconds for running tasks"
    )
    timeout_worker_interval_s: float = Field(
        default=30.0, alias="TIMEOUT_WORKER_INTERVAL_S",
        description="Interval in seconds between timeout worker cycles"
    )

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()