"""Windows desktop host for the local APISwitch gateway."""

from __future__ import annotations

import os
import shutil
import socket
import stat
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

from cryptography.fernet import Fernet


_DESKTOP_ENVIRONMENT = {
    "APISWITCH_APP_NAME": "APISwitch",
    "APISWITCH_LISTEN_HOST": "127.0.0.1",
    "APISWITCH_PORT": "0",
    "APISWITCH_AUTH_ENABLED": "false",
    "APISWITCH_ADMIN_AUTH_ENABLED": "false",
    "APISWITCH_FILE_MAX_UPLOAD_BYTES": str(20 * 1024 * 1024),
    "APISWITCH_RELOAD": "false",
    "APISWITCH_STREAM_FAILURE_MODE": "strict_compat_mode",
}
_WINDOWS_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_WINDOWS_RUN_VALUE = "APISwitch"
_IPC_PORT = 48183
_instance_mutex = None


def runtime_info() -> dict[str, object]:
    """Read only non-sensitive desktop runtime state for the admin API."""
    runtime = _runtime_dir() / "runtime.json"
    if runtime.is_file():
        import json
        try:
            return json.loads(runtime.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            pass
    return {"base_url": "http://127.0.0.1:8080", "port": 8080, "data_directory": str(_runtime_dir()), "desktop": False}


def _resource_root() -> Path:
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))


def _runtime_dir() -> Path:
    user_home = Path(os.getenv("USERPROFILE") or Path.home())
    root = user_home / ".apiswitch"
    # Generation 2 deliberately never imports the historical desktop store.
    # bootstrap.py handles an existing database in this directory by creating a
    # SQLite backup before a clean schema is created.
    root.mkdir(parents=True, exist_ok=True)
    return root


def _configure_master_key(runtime: Path) -> None:
    """Provide a stable per-user encryption key without embedding one in the executable."""
    if os.getenv("APISWITCH_MASTER_KEY"):
        return

    key_path = runtime / "master.key"
    try:
        key = key_path.read_bytes().strip()
    except FileNotFoundError:
        key = Fernet.generate_key()
        try:
            with key_path.open("xb") as key_file:
                key_file.write(key)
        except FileExistsError:
            key = key_path.read_bytes().strip()

    try:
        Fernet(key)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"Invalid APISwitch desktop master key: {key_path}") from exc
    if sys.platform=="win32":
        principal="\\".join(value for value in (os.getenv("USERDOMAIN"),os.getenv("USERNAME")) if value)
        if not principal:raise RuntimeError("无法确定当前 Windows 用户，不能保护主密钥")
        result=subprocess.run(["icacls",str(key_path),"/inheritance:r","/grant:r",f"{principal}:(R,W)"],capture_output=True,text=True,creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0),check=False)
        if result.returncode!=0:raise RuntimeError(f"无法限制 APISwitch 主密钥 ACL：{result.stderr.strip()}")
    else:key_path.chmod(stat.S_IRUSR|stat.S_IWUSR)
    os.environ["APISWITCH_MASTER_KEY"] = key.decode("ascii")


def _startup_command() -> str:
    if getattr(sys, "frozen", False):
        arguments = [str(Path(sys.executable).resolve()), "--background"]
    else:
        arguments = [str(Path(sys.executable).resolve()), "-m", "apiswitch.desktop", "--background"]
    return subprocess.list2cmdline(arguments)


def _read_startup_command() -> str | None:
    if sys.platform != "win32":
        return None
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _WINDOWS_RUN_KEY) as key:
            value, _ = winreg.QueryValueEx(key, _WINDOWS_RUN_VALUE)
    except FileNotFoundError:
        return None
    return str(value)


def _write_startup_command(command: str | None) -> None:
    if sys.platform != "win32":
        raise RuntimeError("Desktop auto-start is only supported on Windows")
    import winreg

    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, _WINDOWS_RUN_KEY) as key:
        if command is None:
            try:
                winreg.DeleteValue(key, _WINDOWS_RUN_VALUE)
            except FileNotFoundError:
                pass
        else:
            winreg.SetValueEx(key, _WINDOWS_RUN_VALUE, 0, winreg.REG_SZ, command)


def is_startup_enabled() -> bool:
    return _read_startup_command() == _startup_command()


def set_startup_enabled(enabled: bool) -> None:
    _write_startup_command(_startup_command() if enabled else None)


class DesktopTray:
    def __init__(self, window) -> None:
        import pystray
        from PIL import Image, ImageDraw

        image = Image.new("RGBA", (64, 64), (23, 116, 255, 255))
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle((8, 8, 56, 56), radius=12, fill=(255, 255, 255, 255))
        draw.polygon(((18, 24), (42, 24), (36, 18), (47, 28), (36, 38), (42, 32), (18, 32)), fill=(23, 116, 255, 255))

        self.window = window
        self.exiting = False
        self._thread: threading.Thread | None = None
        self._ready = threading.Event()
        self._startup_error: list[BaseException] = []
        self.icon = pystray.Icon(
            "APISwitch",
            image,
            "APISwitch",
            pystray.Menu(
                pystray.MenuItem("打开 APISwitch", self.show, default=True),
                pystray.MenuItem("隐藏窗口", self.hide),
                pystray.MenuItem("复制网关地址",self.copy_gateway_address),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("开机自启动", self.toggle_startup, checked=lambda _: is_startup_enabled()),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("退出", self.exit),
            ),
        )

    def start(self) -> None:
        def setup(icon) -> None:
            icon.visible = True
            self._ready.set()

        def run() -> None:
            try:
                self.icon.run(setup=setup)
            except BaseException as exc:  # pragma: no cover - depends on the Windows shell
                self._startup_error.append(exc)
                self._ready.set()

        self._thread = threading.Thread(target=run, name="apiswitch-tray", daemon=True)
        self._thread.start()
        if not self._ready.wait(timeout=10):
            raise RuntimeError("APISwitch system tray did not start within 10 seconds")
        if self._startup_error:
            raise RuntimeError(f"APISwitch system tray failed to start: {self._startup_error[0]}") from self._startup_error[0]

    def stop(self) -> None:
        self.icon.stop()
        if self._thread is not None and self._thread is not threading.current_thread():
            self._thread.join(timeout=5)

    def show(self, *_args) -> None:
        _show_desktop_window(self.window)

    def hide(self, *_args) -> None:
        self.window.hide()

    def on_closing(self) -> bool | None:
        if self.exiting:
            return None
        threading.Thread(target=self.hide, name="apiswitch-hide-window", daemon=True).start()
        return False

    def on_minimized(self) -> None:
        self.hide()

    def copy_gateway_address(self,icon,_item)->None:
        import json
        address=str(runtime_info().get("base_url") or "http://127.0.0.1:8080")
        try:
            self.window.evaluate_js(f"navigator.clipboard.writeText({json.dumps(address)})")
            icon.notify(f"已复制 {address}","APISwitch")
        except Exception as exc:icon.notify(f"复制失败：{exc}","APISwitch")

    def toggle_startup(self, icon, _item) -> None:
        try:
            set_startup_enabled(not is_startup_enabled())
            icon.update_menu()
        except OSError as exc:
            icon.notify(f"无法修改开机自启动：{exc}", "APISwitch")

    def exit(self, icon, _item) -> None:
        self.exiting = True
        icon.stop()
        self.window.destroy()


def configure_desktop_environment() -> tuple[Path, Path]:
    """Configure isolated data and bundled frontend paths before importing the app."""
    runtime = _runtime_dir()
    frontend = _resource_root() / "frontend" / "dist"
    files = runtime / "files"
    files.mkdir(parents=True, exist_ok=True)
    os.environ.update(_DESKTOP_ENVIRONMENT)
    os.environ["APISWITCH_DATABASE_URL"] = f"sqlite:///{(runtime / 'apiswitch.db').as_posix()}"
    os.environ["APISWITCH_FILE_STORAGE_DIR"] = str(files)
    os.environ["APISWITCH_FRONTEND_DIST_DIR"] = str(frontend)
    _configure_master_key(runtime)
    return runtime, frontend


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _select_port(preferred: int = 8080) -> int:
    """Prefer the documented port, then let the OS choose a safe loopback port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        # SO_REUSEADDR has different semantics on Windows and can make this
        # probe succeed even while another process is already listening.  The
        # subsequent uvicorn bind then fails with WSAEADDRINUSE.  An ordinary
        # bind is the correct availability check for a desktop-only listener.
        try:
            sock.bind(("127.0.0.1", preferred))
            return preferred
        except OSError:
            return _free_port()


def _write_runtime(port: int) -> None:
    import json
    root = _runtime_dir()
    temporary = root / "runtime.json.tmp"
    temporary.write_text(json.dumps({"pid": os.getpid(), "port": port, "base_url": f"http://127.0.0.1:{port}", "version": "0.1.0", "started_at": time.time(), "data_directory": str(root), "desktop": True}), encoding="utf-8")
    os.replace(temporary, root / "runtime.json")


def _refresh_agents_for_port_change(previous_base_url: str | None, base_url: str) -> int:
    if previous_base_url == base_url:
        return 0
    from apiswitch.db.session import SessionLocal
    from apiswitch.services.agent_configs import refresh_enabled_agent_configs

    with SessionLocal() as db:
        return refresh_enabled_agent_configs(db, base_url)


def _acquire_single_instance() -> bool:
    """Acquire a current-user Windows mutex without relying on a writable EXE directory."""
    global _instance_mutex
    if sys.platform != "win32":
        return True
    import ctypes
    name = f"Local\\APISwitch-{os.getenv('USERNAME', 'user')}"
    handle = ctypes.windll.kernel32.CreateMutexW(None, False, name)
    if not handle:
        raise OSError("无法创建 APISwitch 单实例互斥体")
    if ctypes.windll.kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
        ctypes.windll.kernel32.CloseHandle(handle)
        return False
    _instance_mutex = handle
    return True


def _request_existing_window() -> None:
    try:
        with socket.create_connection(("127.0.0.1", _IPC_PORT), timeout=1) as client:
            client.sendall(b"show")
    except OSError:
        # A stale mutex is handled by Windows when its process exits; never start a second backend.
        pass


def _show_desktop_window(window) -> None:
    """Show the desktop window and recover pywebview's first hidden position.

    On Windows, pywebview creates a hidden WinForms window by briefly showing
    and hiding it.  Its native location can consequently remain at the Windows
    hidden-window coordinates (-32000, -32000).  ``restore`` and ``show`` make
    such a window visible without moving it back onto a monitor.  Re-center the
    first time a background-started window is opened; later opens preserve the
    user's chosen position.
    """
    window.restore()
    window.show()
    if not getattr(window, "_apiswitch_recenter_on_show", False):
        return
    width = max(int(getattr(window, "width", 1100)), 1)
    height = max(int(getattr(window, "height", 720)), 1)
    screen_width, screen_height = 1920, 1080
    if sys.platform == "win32":
        try:
            import ctypes

            screen_width = int(ctypes.windll.user32.GetSystemMetrics(0)) or screen_width
            screen_height = int(ctypes.windll.user32.GetSystemMetrics(1)) or screen_height
        except (AttributeError, OSError):  # pragma: no cover - platform API failure
            pass
    window.move(max((screen_width - width) // 2, 0), max((screen_height - height) // 2, 0))
    window._apiswitch_recenter_on_show = False


def _start_ipc_server(window) -> socket.socket:
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind(("127.0.0.1", _IPC_PORT)); listener.listen(2); listener.settimeout(0.5)
    def serve() -> None:
        while True:
            try:
                client, _ = listener.accept()
            except TimeoutError:
                if getattr(window, "_apiswitch_closing", False): return
                continue
            except OSError: return
            with client:
                if client.recv(16) == b"show":
                    _show_desktop_window(window)
    threading.Thread(target=serve, name="apiswitch-instance-ipc", daemon=True).start()
    return listener


def _wait_for_server(url: str, timeout_seconds: float = 15) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f"{url}/health", timeout=1) as response:  # noqa: S310
                if response.status == 200:
                    return
        except OSError:
            time.sleep(0.15)
    raise RuntimeError("APISwitch desktop backend did not start within 15 seconds")


def run_desktop(*, start_hidden: bool = False) -> None:
    if not _acquire_single_instance():
        _request_existing_window()
        return
    previous_base_url = str(runtime_info().get("base_url") or "")
    _, frontend = configure_desktop_environment()
    if not (frontend / "index.html").is_file():
        raise RuntimeError("Bundled frontend is missing. Build the frontend before packaging APISwitch Desktop.")

    import uvicorn
    import webview
    from apiswitch.app import app

    port = _select_port(8080)
    url = f"http://127.0.0.1:{port}"
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    startup_error: list[BaseException] = []

    def serve() -> None:
        try:
            server.run()
        except BaseException as exc:  # pragma: no cover - depends on local runtime failures
            startup_error.append(exc)

    worker = threading.Thread(target=serve, name="apiswitch-backend", daemon=True)
    worker.start()
    try:
        try:
            _wait_for_server(url)
        except RuntimeError as exc:
            if startup_error:
                raise RuntimeError(f"APISwitch desktop backend failed to start: {startup_error[0]}") from startup_error[0]
            raise exc
        _refresh_agents_for_port_change(previous_base_url, url)
        _write_runtime(port)
        window = webview.create_window("APISwitch", f"{url}/ui/", min_size=(1100, 720), hidden=start_hidden)
        window._apiswitch_recenter_on_show = start_hidden
        ipc_listener = _start_ipc_server(window)
        tray = DesktopTray(window)
        window.events.closing += tray.on_closing
        window.events.minimized += tray.on_minimized
        tray.start()
        try:
            webview.start()
        finally:
            window._apiswitch_closing = True
            ipc_listener.close()
            tray.stop()
    finally:
        server.should_exit = True
        worker.join(timeout=5)


if __name__ == "__main__":
    run_desktop(start_hidden="--background" in sys.argv[1:])
