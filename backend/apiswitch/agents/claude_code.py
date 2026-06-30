from pathlib import Path

from apiswitch.agents.base import AgentConfigurator


class ClaudeCodeConfigurator(AgentConfigurator):
    agent_type = "claude_code"

    def detect_config_path(self) -> Path | None:
        return Path.home() / ".claude" / "settings.json"
