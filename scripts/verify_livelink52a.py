"""Exercise the configured MCP over stdio; keep run evidence in the repository."""
import argparse
import asyncio
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

REPO = Path(__file__).resolve().parents[1]


def snapshot():
    command = "[pscustomobject]@{processes=@(Get-Process -ErrorAction SilentlyContinue | Where-Object {$_.ProcessName -match '^(comsol|matlab|java)'} | Select-Object ProcessName,Id,Path); port=@(Get-NetTCPConnection -LocalPort 2036 -State Listen -ErrorAction SilentlyContinue | Select-Object LocalAddress,OwningProcess)}|ConvertTo-Json -Depth 4 -Compress"
    p = subprocess.run(["powershell", "-NoProfile", "-Command", command], capture_output=True, text=True)
    return json.loads(p.stdout)


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--matlab-script", type=Path)
    args = parser.parse_args()
    run = REPO / "runs" / f"mcp-{time.time_ns()}"
    run.mkdir(parents=True)
    report = {"run": str(run), "before": snapshot()}
    env = dict(os.environ)
    env["COMSOL_LIVELINK_WORKDIR"] = str(run)
    env["COMSOL_ROOT"] = env.get("COMSOL_ROOT", r"D:\Program Files\COMSOL\COMSOL52a\Multiphysics")
    env["PYTHONIOENCODING"] = "utf-8"
    env.pop("JAVA_TOOL_OPTIONS", None)
    # A fresh server makes cleanup ownership unambiguous.
    if report["before"]["port"] or report["before"]["processes"]:
        raise RuntimeError("Existing COMSOL/MATLAB/Java process or port 2036; leave it untouched")
    started = None
    try:
        with (run / "mcp.stderr.log").open("w", encoding="utf-8") as err:
            params = StdioServerParameters(command=sys.executable, args=[str(REPO / "scripts/start_comsol52a.py")], env=env, cwd=str(REPO))
            async with stdio_client(params, errlog=err) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    async def call(name, arguments=None):
                        result = await session.call_tool(name, arguments or {})
                        if result.isError:
                            raise RuntimeError(str(result))
                        value = json.loads(next(c.text for c in result.content if c.type == "text"))
                        report[name] = value
                        return value
                    await call("status")
                    started = await call("start_server")
                    report["during"] = snapshot()
                    if not started.get("started") or not started.get("listening"):
                        raise RuntimeError(str(started))
                    if args.matlab_script:
                        result = await call("run_matlab", {"script": args.matlab_script.read_text(encoding="utf-8"), "timeout_seconds": 600})
                    else:
                        result = await call("smoke_test", {"timeout_seconds": 300})
                    if result.get("returncode") != 0:
                        raise RuntimeError(str(result))
                    output = Path(result["script_path"]).parent
                    report["artifacts"] = {p.name: p.stat().st_size for p in output.iterdir() if p.is_file()}
                    if not args.matlab_script:
                        numeric = json.loads((output / "comsol_smoke_result.json").read_text())
                        report["numeric"] = numeric
                        assert abs(numeric["midpoint_u"] - 50) < 1e-8
                        assert numeric["max_abs_error"] < 1e-8
                        assert (output / "codex_livelink_smoke.mph").stat().st_size > 0
                    report["success"] = True
    except BaseException as exc:
        report["success"] = False
        report["error"] = str(exc)
        raise
    finally:
        if started and started.get("pid"):
            pid = int(started["pid"])
            subprocess.run(["powershell", "-NoProfile", "-Command", f"$p=Get-Process -Id {pid} -ErrorAction SilentlyContinue; if($p -and $p.ProcessName -eq 'comsolmphserver'){{$p | Stop-Process}}"], capture_output=True)
        report["after"] = snapshot()
        (run / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
