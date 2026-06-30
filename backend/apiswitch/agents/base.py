from dataclasses import dataclass
from pathlib import Path


@dataclass
class AgentConfigPatch:
    agent_type: str
    config_path: Path | None
    content_preview: str


class AgentConfigurator:
    agent_type: str

    def detect_config_path(self) -> Path | None:
        return None

    def build_patch(self, base_url: str, api_key: str, model: str) -> AgentConfigPatch:
        return AgentConfigPatch(
            agent_type=self.agent_type,
            config_path=self.detect_config_path(),
            content_preview=f"base_url={base_url}\napi_key=<hidden>\nmodel={model}\n",
        )
