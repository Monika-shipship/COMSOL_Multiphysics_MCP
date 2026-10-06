---
name: comsol-automation
description: Operate COMSOL Multiphysics 5.2a on Windows through the COMSOL_LiveLink MCP and MATLAB LiveLink. Use for MPH inspection, protected-copy edits, solving, parameter sweeps, startup diagnosis, and verified exports. Check APIs against 5.2a.
---

# COMSOL automation for 5.2a

Use COMSOL to produce numerical solutions. Independent Python calculations or plots cannot establish that a COMSOL solve or export succeeded.

## Local baseline and source

Verified on 2026-10-06 with COMSOL 5.2a, file version `5.2.1.152`, Windows x64. Treat this as dated evidence; inspect the current registration and call `status` before relying on paths or server state.

- Maintained repository: `D:\Repos\AIwork\Codex-plugins\COMSOL_Multiphysics_MCP` (called `REPO` below).
- Skill source: `REPO\skills\comsol-automation`; local Codex discovery entry: `C:\Users\Administrator\.codex\skills\comsol-automation`.
- GitHub: https://github.com/Monika-shipship/COMSOL_Multiphysics_MCP, branch `codex/comsol-52a-base-compat`.
- COMSOL root: `D:\Program Files\COMSOL\COMSOL52a\Multiphysics`.
- Executables below that root: `bin\win64\comsolmphserver.exe` and `bin\win64\comsolbatch.exe`; LiveLink files: `mli`.
- COMSOL Java: bundled Java 8, `1.8.0_66`. A system Java installation or successful Python DLL load does not validate this Java native startup chain.
- MATLAB: `D:\Program Files\MATLAB\R2025b\bin\matlab.exe`. This combination passed local tests; it is not an official compatibility claim.
- MCP name: `COMSOL_LiveLink`; Python: `REPO\runtime\python52a\Scripts\python.exe`.
- MCP arguments: `REPO\scripts\start_comsol52a.py --backend livelink`.
- Model/script/log outputs: `REPO\runtime\comsol-livelink`; isolated verifier evidence: `REPO\runs`.
- Default server port: `2036`. Confirm its current owning process before connecting or stopping anything.

The skill is local guidance originally authored with Codex, maintained in this repository. It is not an official COMSOL skill. On other machines, resolve the actual checkout and registration instead of creating these machine-specific paths.

## Choose a route

For registration or status questions, inspect only the `COMSOL_LiveLink` configuration table and use the read-only `status` tool when available. Do not print the entire Codex configuration because other entries can contain credentials. Do not start a server or run a smoke model merely to inspect registration.

For an authorized model operation, prefer the verified route: MCP, MATLAB LiveLink, then COMSOL 5.2a server. Read the current tool schemas; the four tools are:

- `status`: report paths, process and port state. It does not prove a solver works.
- `start_server`: start or reuse a listener; verify that the listener belongs to COMSOL.
- `run_matlab`: connect through LiveLink and execute supplied MATLAB code. It can start the server and creates a separate script/output directory.
- `smoke_test`: create and solve a small 1D PDE, saving MPH, CSV, JSON and logs. Use when validating the bridge itself.

The raw `comsolbatch.exe` route still had a separate mesh-extension failure in the 2026-10-06 investigation. Do not recommend it as the default verified route or claim the LiveLink fix repaired it. Use batch or standalone Java only when the task needs that route and validate it independently against 5.2a. Use Desktop for requested interactive work.

If tools are absent, inspect registration with `codex mcp get COMSOL_LiveLink` or a targeted config read. An existing chat may require a new chat or app reload to discover changes; tell the user rather than creating a new chat automatically. A successful stdio MCP client test proves the service works, but does not prove the current chat has loaded its tools.

## Startup diagnosis

Read `REPO\docs\comsol52a-startup.md` when diagnosing native startup, and the repository README when inspecting installation or registration.

The repository launcher supplies `runtime\native-loader\dllpath-rust-agent.dll` through process-local `JAVA_TOOL_OPTIONS`. It prepares native DLL search directories and preload order. Avoid adding a second `-agentpath` or running the server script directly without the launcher. Preserve installed COMSOL DLLs, system PATH, registry and user MATLAB settings.

For `csutil.dll` / `FlLicense` failures, capture the exact native loader error and inspect dependencies and loading order. Missing-library wording alone does not establish that a DLL file is absent. Check COMSOL build, Java, permissions and license errors separately. Explain the effect before any MCP registration change; this skill itself grants no permission to change registration.

Keep new runtime installations and diagnostic outputs in the user's chosen D-drive checkout. COMSOL still writes profile, recovery and log data under `C:\Users\Administrator\.comsol\v52a` on this machine. Do not promise zero C-drive writes or delete that directory as disposable cache; it contains historical recovery models.

## Model handling and validation

- Preserve source MPH files. Load a clearly named protective copy and save to a new output. For the EYM project, `before\sources\E-YM.mph` is the protected source; hash it before and after work.
- Resolve feature tags, selections, variables and methods from the model, a COMSOL-generated script, installed 5.2a documentation or a read-only query. Examples from 5.6/6.x are unverified for 5.2a.
- Keep units, physics, solver settings and sweep ranges traceable to the source or the user's requested changes.
- For each test, record exit codes, logs, relevant processes, port 2036 state and actual output files. Keep failed-run logs. Historical status JSON, old PIDs, a listening port or exit code 0 alone do not establish success.
- Verify numerical values and nonempty MPH/data files. Inspect warnings and report any effect on validity; license/module failures or missing requested output prevent a success claim. Verify image files separately before claiming image export.
- Stop only processes started by the test, with identity checks; never terminate an unrelated COMSOL/MATLAB/Java session to make a check pass. Snapshot state after cleanup.

The bridge smoke model is `-u''=0` on `[0,1]`, with `u(0)=100`, `u(1)=0`. Require midpoint `u=50` and maximum absolute error below `1e-8`, plus newly generated MPH/CSV/JSON and successful MATLAB logs. The 2026-10-06 test returned midpoint `50.0000000000001` and error `7.105427357601e-13`; future tests must produce their own evidence.

For an authorized checkout verification, `REPO\scripts\verify_livelink52a.py` exercises MCP over stdio and writes evidence under `runs`. It tests the checkout launcher with an isolated work directory, not necessarily the exact installed Codex configuration. For registration verification, read and use the actual configured command, arguments and environment; disclose any overrides. Do not rerun a solver for a documentation-only change.
