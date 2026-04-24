from __future__ import annotations

import os
import shlex
import subprocess
from pathlib import Path
from typing import Any


class ProcessControlError(RuntimeError):
    pass


def build_service_control_read_model() -> dict[str, Any]:
    pid_file = pid_file_path()
    log_file = log_file_path()
    pid = read_pid(pid_file)
    running = pid is not None and is_process_running(pid)
    if pid is not None and not running and pid_file.exists():
        pid_file.unlink()
        pid = None
    healthy = running
    return {
        "pid": pid,
        "running": running,
        "healthy": healthy,
        "pid_file": str(pid_file),
        "log_file": str(log_file),
        "status_summary": _status_summary(running, healthy),
        "available_actions": ["start", "stop", "restart"],
    }


def start_service() -> dict[str, Any]:
    return _run_script(start_script_path())


def stop_service() -> dict[str, Any]:
    return _run_script(stop_script_path())


def schedule_restart() -> dict[str, Any]:
    command = " && ".join(
        [
            shlex.quote(str(stop_script_path())),
            "sleep 1",
            shlex.quote(str(start_script_path())),
        ]
    )
    subprocess.Popen(
        ["/bin/bash", "-lc", command],
        cwd=repo_root(),
        env=os.environ.copy(),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    return {
        "message": "restart scheduled",
        "poll_url": "/admin/service-control/status",
    }


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def start_script_path() -> Path:
    return repo_root() / "scripts" / "start.sh"


def stop_script_path() -> Path:
    return repo_root() / "scripts" / "stop.sh"


def pid_file_path() -> Path:
    return _resolve_control_path(os.getenv("PIDFILE"), "data/ra.pid")


def log_file_path() -> Path:
    return _resolve_control_path(os.getenv("LOGFILE"), "data/ra.log")


def read_pid(pid_file: Path) -> int | None:
    if not pid_file.exists():
        return None
    raw_value = pid_file.read_text(encoding="utf-8").strip()
    if not raw_value:
        return None
    try:
        return int(raw_value)
    except ValueError:
        return None


def is_process_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _resolve_control_path(env_value: str | None, default_relative_path: str) -> Path:
    raw_path = Path(env_value) if env_value else Path(default_relative_path)
    if raw_path.is_absolute():
        return raw_path
    return repo_root() / raw_path


def _run_script(script_path: Path) -> dict[str, Any]:
    completed = subprocess.run(
        [str(script_path)],
        cwd=repo_root(),
        env=os.environ.copy(),
        capture_output=True,
        text=True,
        check=False,
    )
    stdout = completed.stdout.strip()
    stderr = completed.stderr.strip()
    message = stdout or stderr or f"{script_path.name} exited with code {completed.returncode}"
    if completed.returncode != 0:
        raise ProcessControlError(message)
    return {
        "message": message,
        "script": str(script_path),
    }


def _status_summary(running: bool, healthy: bool) -> str:
    if running and healthy:
        return "Running and healthy"
    if running:
        return "Running but unhealthy"
    return "Stopped"
