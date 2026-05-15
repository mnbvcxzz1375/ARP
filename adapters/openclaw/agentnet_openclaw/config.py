from pydantic import BaseModel, Field


class OpenClawConfig(BaseModel):
    mode: str = "cli"
    command: str = "openclaw"
    working_dir: str
    allow_paths: list[str] = Field(default_factory=list)
    deny_paths: list[str] = Field(default_factory=list)
    require_approval: list[str] = Field(default_factory=list)
    env_policy: str = "minimal"
    env_vars: dict[str, str] = Field(default_factory=dict)
    pass_env: list[str] = Field(default_factory=list)


class AgentConfig(BaseModel):
    number: str
    runtime: str = "openclaw"


class AdapterConfig(BaseModel):
    agent: AgentConfig
    openclaw: OpenClawConfig

