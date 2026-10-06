import json
from pathlib import Path
from subprocess import CompletedProcess

from src import livelink_server as server


def test_status_does_not_create_work_directory(monkeypatch, tmp_path):
    work = tmp_path / "absent"
    monkeypatch.setattr(server, "WORK_DIR", work)
    monkeypatch.setattr(server, "_powershell", lambda *a, **k: CompletedProcess([], 0, "{}", ""))
    assert json.loads(server.status())["powershell_returncode"] == 0
    assert not work.exists()


def test_matlab_runs_preserve_separate_scripts_and_failure_logs(monkeypatch, tmp_path):
    monkeypatch.setattr(server, "WORK_DIR", tmp_path)
    monkeypatch.setattr(server, "_start_server_if_needed", lambda *a: {"listening": True})
    monkeypatch.setattr(server.subprocess, "run", lambda *a, **k: CompletedProcess([], 2, "failure output", "native error"))
    first = json.loads(server.run_matlab("disp('first');"))
    second = json.loads(server.run_matlab("disp('second');"))
    assert first["returncode"] == 2
    assert first["script_path"] != second["script_path"]
    assert "first" in Path(first["script_path"]).read_text()
    assert (Path(first["script_path"]).parent / "matlab.stderr.log").read_text() == "native error"
