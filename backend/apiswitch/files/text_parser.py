from pathlib import Path

from apiswitch.files.parser_base import FileParser, ParsedFile


class TextFileParser(FileParser):
    supported_extensions = {".txt", ".md", ".py", ".ts", ".js", ".json"}

    def parse(self, path: Path) -> ParsedFile:
        text = path.read_text(encoding="utf-8")
        return ParsedFile(path=path, text=text, metadata={"parser": "text"})
