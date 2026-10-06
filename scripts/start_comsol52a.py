"""Start a repository-local MCP process with the COMSOL 5.2a loader."""
from pathlib import Path
import argparse
import os
import sys

REPO = Path(__file__).resolve().parents[1]


def configure() -> None:
    root = Path(os.environ.get("COMSOL_ROOT", r"D:\Program Files\COMSOL\COMSOL52a\Multiphysics"))
    loader = REPO / "runtime/native-loader/dllpath-rust-agent.dll"
    for path in (root / "bin/win64/comsolmphserver.exe", root / "java/win64/jre/bin/server/jvm.dll", loader):
        if not path.is_file():
            raise FileNotFoundError(path)
    os.environ["COMSOL_ROOT"] = str(root)
    os.environ.setdefault("COMSOL_LIVELINK_WORKDIR", str(REPO / "runtime/comsol-livelink"))
    # Only this MCP process and its children inherit the agent.
    option = f'-agentpath:"{loader}"'
    existing = os.environ.get("JAVA_TOOL_OPTIONS", "")
    if "-agentpath:" in existing:
        raise RuntimeError("Remove the old -agentpath from this MCP's JAVA_TOOL_OPTIONS; this launcher supplies it.")
    os.environ["JAVA_TOOL_OPTIONS"] = (existing + " " + option).strip()
    sys.path.insert(0, str(REPO))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", choices=("livelink", "mph"), default="livelink")
    args = parser.parse_args()
    configure()
    if args.backend == "livelink":
        from src.livelink_server import mcp
        mcp.run()
    else:
        from src.server import main
        main()
