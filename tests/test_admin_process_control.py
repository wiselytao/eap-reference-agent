import subprocess

import pytest

from reference_agent.admin import process_control


def test_schedule_restart_spawns_detached_command_with_initial_grace_delay(monkeypatch):
    captured: dict[str, object] = {}

    def fake_popen(args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return object()

    monkeypatch.setattr(process_control.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(process_control, "repo_root", lambda: process_control.Path("/repo"))
    monkeypatch.setattr(process_control, "start_script_path", lambda: process_control.Path("/repo/scripts/start.sh"))
    monkeypatch.setattr(process_control, "stop_script_path", lambda: process_control.Path("/repo/scripts/stop.sh"))

    result = process_control.schedule_restart()

    assert result == {
        "message": "restart scheduled",
        "poll_url": "/admin/service-control/status",
    }
    assert captured["args"][0:2] == ["/bin/bash", "-lc"]
    command = captured["args"][2]
    assert "sleep" in command
    assert command.index("sleep") < command.index("/repo/scripts/stop.sh")
    assert command.index("/repo/scripts/stop.sh") < command.index("/repo/scripts/start.sh")
    assert captured["kwargs"]["cwd"] == process_control.Path("/repo")
    assert captured["kwargs"]["start_new_session"] is True
    assert captured["kwargs"]["stdout"] is subprocess.DEVNULL
    assert captured["kwargs"]["stderr"] is subprocess.DEVNULL


def test_build_service_control_read_model_is_side_effect_free_for_stale_pid(tmp_path, monkeypatch):
    pid_file = tmp_path / "ra.pid"
    log_file = tmp_path / "ra.log"
    pid_file.write_text("4242", encoding="utf-8")

    monkeypatch.setattr(process_control, "pid_file_path", lambda: pid_file)
    monkeypatch.setattr(process_control, "log_file_path", lambda: log_file)
    monkeypatch.setattr(process_control, "is_process_running", lambda pid: False)

    status = process_control.build_service_control_read_model()

    assert status["pid"] == 4242
    assert status["running"] is False
    assert status["healthy"] is False
    assert status["status_summary"] == "Stopped"
    assert pid_file.exists()


def test_run_script_raises_process_control_error_for_non_zero_exit(monkeypatch):
    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(args=args[0], returncode=1, stdout="", stderr="permission denied")

    monkeypatch.setattr(process_control.subprocess, "run", fake_run)

    with pytest.raises(process_control.ProcessControlError, match="permission denied"):
        process_control._run_script(process_control.Path("/repo/scripts/start.sh"))
