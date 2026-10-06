# COMSOL MCP for 5.2a on Windows

This fork maintains a local MCP setup for **COMSOL Multiphysics 5.2a, build 5.2.1.152, Windows x64**. It includes a MATLAB LiveLink server and the original Python/MPh tool server. The native startup fix in this release is specific to 5.2a; it has not been validated with COMSOL 5.6 or 6.x.

[中文说明](README_CN.md) · [Changes](CHANGELOG.md) · [Startup diagnosis](docs/comsol52a-startup.md)

The local failure was `csutil.dll: Can't find dependent libraries`, followed by `NoClassDefFoundError: ...FlLicense`. The DLLs were present. A Java agent now prepares the DLL search directories and preloads COMSOL's native libraries before Java initializes them. It runs inside the MCP process and its children. It does not replace COMSOL DLLs or change the system PATH, registry, or MATLAB user settings.

## Requirements

You need a working COMSOL 5.2a installation and the licenses required by your model. The tested environment uses Python 3.13 x64, MPh 1.3.1, JPype 1.5.2 and COMSOL's bundled Java 8 (`1.8.0_66`). The LiveLink route was tested locally with MATLAB R2025b; that observation is not an official compatibility statement for this much newer MATLAB release.

The Python/MPh backend does not require MATLAB. The four-tool LiveLink backend requires MATLAB and LiveLink for MATLAB.

## Install in this checkout

Keep the checkout on the drive where you want the runtime and output files. The scripts create `runtime/python52a`, `runtime/tmp` and `runtime/comsol-livelink` inside it. They do not install another copy of COMSOL.

```powershell
git clone --branch codex/comsol-52a-base-compat https://github.com/Monika-shipship/COMSOL_Multiphysics_MCP.git D:\Repos\COMSOL_Multiphysics_MCP
cd D:\Repos\COMSOL_Multiphysics_MCP
.\scripts\setup_comsol52a.ps1 -Python 'D:\Program Files\Python313\python.exe'
```

Download `dllpath-rust-agent.dll` from the matching GitHub release and place it in `runtime/native-loader`. To build it from the included Rust source, use an existing Rust x64 Windows GNU toolchain:

```powershell
.\scripts\build_native_loader.ps1
```

The build script uses Rust's bundled linker. COMSOL binaries and licenses are not included in the release asset.

## Codex configuration

Adjust these paths to your checkout and installations. The launcher derives the loader location from its own checkout and passes it through `JAVA_TOOL_OPTIONS` to its child processes. Do not also configure an old `-agentpath` value.

```toml
[mcp_servers.COMSOL_LiveLink]
command = 'D:\Repos\COMSOL_Multiphysics_MCP\runtime\python52a\Scripts\python.exe'
args = ['D:\Repos\COMSOL_Multiphysics_MCP\scripts\start_comsol52a.py', '--backend', 'livelink']
startup_timeout_sec = 120
tool_timeout_sec = 660

[mcp_servers.COMSOL_LiveLink.env]
COMSOL_ROOT = 'D:\Program Files\COMSOL\COMSOL52a\Multiphysics'
MATLAB_EXE = 'D:\Program Files\MATLAB\R2025b\bin\matlab.exe'
```

Open a new Codex task after changing registration so it loads the tools. `status` reports the current paths, processes and port. `start_server` starts the COMSOL server. `run_matlab` connects through LiveLink and runs supplied MATLAB code. `smoke_test` solves a small 1D PDE and writes its model and numerical results.

To use the larger Python/MPh server, set `--backend` to `mph`. That backend includes model, geometry, mesh, study and export tools. The [original tool reference](docs/upstream-guide.md) describes the inherited tools; examples written for newer COMSOL versions still need checking against 5.2a.

## Verify the installation

Close your own COMSOL, MATLAB and Java sessions before running the isolated verification script. It refuses to proceed if it finds an existing session or listener on port 2036.

```powershell
$env:COMSOL_ROOT = 'D:\Program Files\COMSOL\COMSOL52a\Multiphysics'
$env:MATLAB_EXE = 'D:\Program Files\MATLAB\R2025b\bin\matlab.exe'
.\runtime\python52a\Scripts\python.exe .\scripts\verify_livelink52a.py
```

This uses the MCP stdio protocol to call `status`, `start_server` and `smoke_test`. The expected midpoint is `u=50` for `-u''=0` on `[0,1]`, with endpoints 100 and 0. Each run gets a new directory under `runs/`, including logs, output file sizes, numerical checks and process/port snapshots. The script stops only the server it started. Failed logs remain available.

A zero launcher exit code or an open port alone does not prove that COMSOL solved a model. Check the solver log, numerical values and nonempty output MPH together. The raw `comsolbatch.exe` route failed separately at mesh extension during this investigation; see the diagnosis for the tested routes and limits.

## Working with models

Load a copy of your source MPH and save results under a new name. Preserve the physics, boundary selections and solver settings unless the task calls for changing them. Numerical results must come from COMSOL. Python plots or independent calculations are not substitutes for a missing COMSOL solve.

To undo this integration, remove its MCP registration. The runtime and logs stay inside the checkout and can be removed after stopping its processes. No COMSOL installation files need restoring.

## Upstream

This project is based on [wjc9011/COMSOL_Multiphysics_MCP](https://github.com/wjc9011/COMSOL_Multiphysics_MCP). The inherited source is MIT licensed; see [LICENSE](LICENSE). COMSOL and MATLAB require their own licenses. The older general-purpose documentation is retained in [English](docs/upstream-guide.md) and [Chinese](docs/upstream-guide-zh.md).
