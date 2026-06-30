from pathlib import Path

from apiswitch.agents.base import AgentConfigurator


class CodexConfigurator(AgentConfigurator):
    agent_type = "codex"

    def detect_config_path(self) -> Path | None:
        return Path.home() / ".codex" / "config.toml"
