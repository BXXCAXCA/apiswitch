from dataclasses import dataclass
from pathlib import Path


@dataclass
class ParsedFile:
    path: Path
    text: str
    metadata: dict[str, str]


class FileParser:
    supported_extensions: set[str] = set()

    def parse(self, path: Path) -> ParsedFile:
        raise NotImplementedError
