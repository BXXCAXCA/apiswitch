"""Fail CI when source files or packaged artifacts contain recognizable secrets."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

_PATTERN_TEXT = {
    "OpenAI-style API key": r"\bsk-[A-Za-z0-9_-]{20,}\b",
    "Anthropic API key": r"\bsk-ant-[A-Za-z0-9_-]{20,}\b",
    "Google API key": r"\bAIza[0-9A-Za-z_-]{35}\b",
    "AWS access key": r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b",
    "GitHub token": r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{30,}\b",
    "GitHub fine-grained token": r"\bgithub_pat_[A-Za-z0-9_]{50,}\b",
    "Slack token": r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b",
    "Private key block": r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----",
}
_PATTERNS = {
    name: re.compile(expression.encode("ascii"))
    for name, expression in _PATTERN_TEXT.items()
}
_SELF = Path(__file__).resolve()
_MAX_TEXT_BYTES = 20 * 1024 * 1024


def _tracked_files(root: Path) -> list[Path]:
    completed = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z"],
        check=True,
        capture_output=True,
    )
    return [root / Path(item.decode("utf-8")) for item in completed.stdout.split(b"\0") if item]


def _candidate_files(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    if (path / ".git").exists():
        return _tracked_files(path)
    return [item for item in path.rglob("*") if item.is_file()]


def _scan(path: Path) -> list[str]:
    if path.resolve() == _SELF:
        return []
    try:
        size = path.stat().st_size
        data = path.read_bytes()
    except OSError as exc:
        return [f"{path}: unreadable ({exc})"]

    # Source files should stay bounded; packaged executables are intentionally scanned in full.
    if size > _MAX_TEXT_BYTES and path.suffix.lower() not in {".exe", ".dll", ".bin"}:
        return []

    findings: list[str] = []
    for name, pattern in _PATTERNS.items():
        match = pattern.search(data)
        if match is None:
            # PyInstaller and Windows resources can contain UTF-16LE strings.
            expression = _PATTERN_TEXT[name].encode("utf-16le")
            if re.search(expression, data) is None:
                continue
        findings.append(f"{path}: {name}")
    return findings


def main(arguments: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="+", type=Path)
    options = parser.parse_args(arguments)

    findings: list[str] = []
    scanned = 0
    for supplied in options.paths:
        target = supplied.resolve()
        if not target.exists():
            parser.error(f"path does not exist: {supplied}")
        for candidate in _candidate_files(target):
            scanned += 1
            findings.extend(_scan(candidate))

    if findings:
        print("Sensitive credential scan failed:", file=sys.stderr)
        for finding in findings:
            print(f"- {finding}", file=sys.stderr)
        return 1

    print(f"Sensitive credential scan passed ({scanned} files).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
