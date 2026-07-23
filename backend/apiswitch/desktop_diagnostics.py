"""Non-interactive diagnostics for the packaged Windows desktop executable."""

from __future__ import annotations

import argparse
import json
import os
import threading
import time
import urllib.request
from pathlib import Path
from typing import Any

from apiswitch.desktop import (
    _acquire_single_instance,
    _select_port,
    _wait_for_server,
    configure_desktop_environment,
)


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _read_endpoint(url: str) -> tuple[int, bytes]:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "APISwitch-Desktop-Diagnostics/1"},
    )
    with urllib.request.urlopen(request, timeout=5) as response:  # noqa: S310
        return int(response.status), response.read(1024 * 1024)


def run_smoke_test(report_path: Path) -> int:
    """Start the bundled backend, verify health and UI assets, then exit."""
    report: dict[str, Any] = {
        "mode": "smoke-test",
        "ok": False,
        "pid": os.getpid(),
    }
    server = None
    worker: threading.Thread | None = None

    try:
        runtime, frontend = configure_desktop_environment()
        if not (frontend / "index.html").is_file():
            raise RuntimeError("Bundled frontend index.html is missing")

        import uvicorn

        from apiswitch.app import app

        port = _select_port(8080)
        base_url = f"http://127.0.0.1:{port}"
        server = uvicorn.Server(
            uvicorn.Config(
                app,
                host="127.0.0.1",
                port=port,
                log_level="warning",
            )
        )
        startup_error: list[BaseException] = []

        def serve() -> None:
            try:
                server.run()
            except BaseException as exc:  # pragma: no cover - process-level failure
                startup_error.append(exc)

        worker = threading.Thread(
            target=serve,
            name="apiswitch-diagnostic-backend",
            daemon=True,
        )
        worker.start()
        try:
            _wait_for_server(base_url)
        except RuntimeError as exc:
            if startup_error:
                raise RuntimeError(
                    f"Diagnostic backend failed to start: {startup_error[0]}"
                ) from startup_error[0]
            raise exc

        health_status, health_body = _read_endpoint(f"{base_url}/health")
        ui_status, ui_body = _read_endpoint(f"{base_url}/ui/")
        health_payload = json.loads(health_body.decode("utf-8"))
        ui_has_app_root = b'id="app"' in ui_body

        report.update(
            {
                "base_url": base_url,
                "port": port,
                "used_fallback_port": port != 8080,
                "data_directory": str(runtime),
                "health_status": health_status,
                "health_payload": health_payload,
                "ui_status": ui_status,
                "ui_has_app_root": ui_has_app_root,
                "ok": health_status == 200 and ui_status == 200 and ui_has_app_root,
            }
        )
        if not report["ok"]:
            report["error"] = "Packaged health or UI verification failed"
    except Exception as exc:  # noqa: BLE001 - diagnostics must always emit a report
        report.update(
            {
                "error_type": type(exc).__name__,
                "error": str(exc),
            }
        )
    finally:
        if server is not None:
            server.should_exit = True
        if worker is not None:
            worker.join(timeout=5)
        _write_report(report_path, report)

    return 0 if report["ok"] else 1


def run_instance_probe(report_path: Path, hold_seconds: float) -> int:
    """Acquire the real Windows mutex and optionally hold it for a second process."""
    acquired = _acquire_single_instance()
    _write_report(
        report_path,
        {
            "mode": "instance-probe",
            "ok": True,
            "pid": os.getpid(),
            "acquired": acquired,
            "hold_seconds": hold_seconds,
        },
    )
    if acquired and hold_seconds > 0:
        time.sleep(hold_seconds)
    return 0


def run_diagnostics_from_args(arguments: list[str]) -> int | None:
    """Return an exit code for a diagnostic command, or None for normal startup."""
    if "--smoke-test" not in arguments and "--instance-probe" not in arguments:
        return None

    parser = argparse.ArgumentParser(prog="APISwitch")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--smoke-test", action="store_true")
    mode.add_argument("--instance-probe", action="store_true")
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--hold-seconds", type=float, default=0)
    options = parser.parse_args(arguments)

    if options.hold_seconds < 0 or options.hold_seconds > 120:
        parser.error("--hold-seconds must be between 0 and 120")

    if options.smoke_test:
        return run_smoke_test(options.report)
    return run_instance_probe(options.report, options.hold_seconds)
