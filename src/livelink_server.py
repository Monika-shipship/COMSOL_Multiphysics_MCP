from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path

from mcp.server.fastmcp import FastMCP


COMSOL_ROOT = Path(os.environ.get("COMSOL_ROOT", r"D:\Program Files\COMSOL\COMSOL52a\Multiphysics"))
MATLAB_EXE = Path(os.environ.get("MATLAB_EXE", r"D:\Program Files\MATLAB\R2025b\bin\matlab.exe"))
DEFAULT_PORT = int(os.environ.get("COMSOL_PORT", "2036"))
WORK_DIR = Path(os.environ.get("COMSOL_LIVELINK_WORKDIR", str(Path(__file__).resolve().parents[1] / "runtime/comsol-livelink")))

COMSOL_MPH_SERVER = COMSOL_ROOT / "bin" / "win64" / "comsolmphserver.exe"
COMSOL_MLI = COMSOL_ROOT / "mli"

mcp = FastMCP("COMSOL LiveLink")


def _powershell(script: str, timeout: int = 60) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
        cwd=str(WORK_DIR) if WORK_DIR.is_dir() else None,
        text=True,
        capture_output=True,
        timeout=timeout,
    )


def _port_listening(port: int) -> bool:
    # netstat is faster and more reliable here than the PowerShell networking
    # cmdlet while a legacy COMSOL server is starting.
    probe = subprocess.run(["netstat", "-ano"], capture_output=True, text=True, timeout=15)
    needle = f":{port}"
    if any(needle in line and "LISTENING" in line.upper() for line in probe.stdout.splitlines()):
        return True
    ps = f"$c=Get-NetTCPConnection -LocalPort {port} -State Listen -ErrorAction SilentlyContinue; if($c){{'yes'}}"
    proc = _powershell(ps, timeout=15)
    return "yes" in proc.stdout


def _ensure_workdir() -> None:
    WORK_DIR.mkdir(parents=True, exist_ok=True)


def _start_server_if_needed(port: int, wait_seconds: int = 60) -> dict:
    _ensure_workdir()
    if _port_listening(port):
        return {"started": False, "listening": True, "port": port, "message": "COMSOL mphserver is already listening."}
    if not COMSOL_MPH_SERVER.exists():
        return {"started": False, "listening": False, "port": port, "error": f"Missing {COMSOL_MPH_SERVER}"}

    args = ["-login", "auto", "-port", str(port), "-np", "1", "-multi", "on", "-silent"]
    stamp = time.time_ns()
    out = WORK_DIR / f"server-{stamp}.stdout.log"
    err = WORK_DIR / f"server-{stamp}.stderr.log"
    with out.open("w", encoding="utf-8") as stdout, err.open("w", encoding="utf-8") as stderr:
        child = subprocess.Popen(
            [str(COMSOL_MPH_SERVER), *args],
            cwd=str(COMSOL_ROOT / "bin" / "win64"),
            stdout=stdout,
            stderr=stderr,
            creationflags=getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
        )

    deadline = time.time() + wait_seconds
    while time.time() < deadline:
        if _port_listening(port):
            return {"started": True, "listening": True, "port": port, "pid": child.pid, "stdout_log": str(out), "stderr_log": str(err)}
        time.sleep(1)

    return {"started": True, "listening": False, "pid": child.pid, "error": "Timed out waiting for COMSOL mphserver.", "stdout_log": str(out), "stderr_log": str(err)}


def _matlab_string(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


@mcp.tool()
def status(port: int = DEFAULT_PORT) -> str:
    """Return COMSOL LiveLink availability, server process, and port status."""
    ps = (
        "$p=Get-Process -Name comsolmphserver -ErrorAction SilentlyContinue | "
        "Select-Object ProcessName,Id,Path | ConvertTo-Json -Compress; "
        f"$c=Get-NetTCPConnection -LocalPort {port} -State Listen -ErrorAction SilentlyContinue | "
        "Select-Object LocalAddress,LocalPort,State,OwningProcess | ConvertTo-Json -Compress; "
        "[pscustomobject]@{process=$p; port=$c} | ConvertTo-Json -Compress"
    )
    proc = _powershell(ps, timeout=20)
    payload = {
        "comsol_root": str(COMSOL_ROOT),
        "comsol_mphserver": str(COMSOL_MPH_SERVER),
        "matlab": str(MATLAB_EXE),
        "mli": str(COMSOL_MLI),
        "work_dir": str(WORK_DIR),
        "port": port,
        "exists": {
            "comsol_mphserver": COMSOL_MPH_SERVER.exists(),
            "matlab": MATLAB_EXE.exists(),
            "mli": COMSOL_MLI.exists(),
        },
        "powershell_returncode": proc.returncode,
        "powershell_stdout": proc.stdout.strip(),
        "powershell_stderr": proc.stderr.strip(),
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


@mcp.tool()
def start_server(port: int = DEFAULT_PORT, wait_seconds: int = 60) -> str:
    """Start COMSOL mphserver with automatic login credentials and wait for the TCP port."""
    return json.dumps(_start_server_if_needed(port, wait_seconds), ensure_ascii=False, indent=2)


@mcp.tool()
def run_matlab(script: str, port: int = DEFAULT_PORT, timeout_seconds: int = 300) -> str:
    """Run MATLAB code after connecting to COMSOL through LiveLink."""
    server = _start_server_if_needed(port)
    if not server.get("listening"):
        return json.dumps({"server": server, "error": "COMSOL server is not listening."}, ensure_ascii=False, indent=2)

    _ensure_workdir()
    run_dir = WORK_DIR / f"run-{time.time_ns()}"
    run_dir.mkdir()
    script_path = run_dir / "codex_livelink_run.m"
    script_path.write_text(
        "\n".join(
            [
                f"addpath({_matlab_string(str(COMSOL_MLI))});",
                f"mphstart('localhost', {port});",
                "import com.comsol.model.*",
                "import com.comsol.model.util.*",
                script,
            ]
        ),
        encoding="utf-8",
    )
    cmd = f"try, run({_matlab_string(str(script_path))}); catch ME, disp('COMSOL_LIVELINK_RUN_FAILED'); disp(getReport(ME,'extended','hyperlinks','off')); exit(2); end"
    proc = subprocess.run(
        [str(MATLAB_EXE), "-batch", cmd],
        cwd=str(run_dir),
        text=True,
        capture_output=True,
        timeout=timeout_seconds,
    )
    (run_dir / "matlab.stdout.log").write_text(proc.stdout, encoding="utf-8")
    (run_dir / "matlab.stderr.log").write_text(proc.stderr, encoding="utf-8")
    return json.dumps(
        {
            "server": server,
            "script_path": str(script_path),
            "returncode": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
        },
        ensure_ascii=False,
        indent=2,
    )


@mcp.tool()
def smoke_test(port: int = DEFAULT_PORT, timeout_seconds: int = 300) -> str:
    """Run a minimal COMSOL PDE model and return explicit numeric results."""
    matlab_code = r"""
model = ModelUtil.create('Model');
model.modelPath(pwd);
model.label('codex_livelink_smoke.mph');

model.geom.create('geom1', 1);
model.geom('geom1').lengthUnit('m');
model.geom('geom1').feature.create('i1', 'Interval');
model.geom('geom1').feature('i1').set('p1', '0');
model.geom('geom1').feature('i1').set('p2', '1');
model.geom('geom1').run;

model.physics.create('c', 'CoefficientFormPDE', 'geom1');
model.physics('c').field('dimensionless').field('u');
model.physics('c').field('dimensionless').component({'u'});
model.physics('c').feature('cfeq1').set('c', '1');
model.physics('c').feature('cfeq1').set('a', '0');
model.physics('c').feature('cfeq1').set('f', '0');

model.physics('c').feature.create('dir1', 'DirichletBoundary', 0);
model.physics('c').feature('dir1').selection.set([1]);
model.physics('c').feature('dir1').set('r', '100');

model.physics('c').feature.create('dir2', 'DirichletBoundary', 0);
model.physics('c').feature('dir2').selection.set([2]);
model.physics('c').feature('dir2').set('r', '0');

model.mesh.create('mesh1', 'geom1');
model.mesh('mesh1').automatic(true);
model.mesh('mesh1').run;

model.study.create('std1');
model.study('std1').feature.create('stat', 'Stationary');
model.study('std1').run;

x = linspace(0, 1, 11);
u = mphinterp(model, 'u', 'coord', x);
mid = mphinterp(model, 'u', 'coord', 0.5);
err = max(abs(u - (100 - 100*x)));
result = [x(:), u(:)];

csvPath = fullfile(pwd, 'comsol_smoke_result.csv');
jsonPath = fullfile(pwd, 'comsol_smoke_result.json');
mphPath = fullfile(pwd, 'codex_livelink_smoke.mph');
writematrix(result, csvPath);
fid = fopen(jsonPath, 'w');
fprintf(fid, '{"model":"-u''''=0 on [0,1], u(0)=100, u(1)=0","midpoint_u":%.15g,"expected_midpoint_u":50,"max_abs_error":%.15g}\n', mid, err);
fclose(fid);
mphsave(model, mphPath);

disp('COMSOL_SMOKE_OK');
fprintf('midpoint_u = %.15g\n', mid);
fprintf('max_abs_error = %.15g\n', err);
fprintf('csv = %s\n', csvPath);
fprintf('json = %s\n', jsonPath);
fprintf('mph = %s\n', mphPath);
"""
    return run_matlab(matlab_code, port=port, timeout_seconds=timeout_seconds)


if __name__ == "__main__":
    mcp.run()
