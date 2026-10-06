# Changes

## 2026-10-06: COMSOL 5.2a automation skill update

- Added the maintained `comsol-automation` skill and Codex UI metadata to this repository.
- Updated the Python, launcher and output paths to the repository-local runtime; made the verified LiveLink route the default.
- Documented the unresolved batch route, COMSOL recovery writes to C:, and the difference between a working MCP service and tools loaded in a chat.
- Added Windows directory-junction installation guidance so the local skill can follow the repository source.

This update changes guidance only. It does not change MCP registration or the native loader.

## 2026-10-06: COMSOL 5.2a native startup repair

This release targets COMSOL Multiphysics 5.2a, file version 5.2.1.152, on Windows x64.

- Added a repository-local Java native loader for the `csutil.dll` dependency-order failure.
- Made the loader use `COMSOL_ROOT` instead of a machine-specific hard-coded install path.
- Added the `COMSOL_LiveLink` stdio entrypoint, a D-drive runtime environment, and per-run logs.
- Added an MCP protocol verifier for the status, server, LiveLink, smoke-model and cleanup checks.
- Added a protected-copy EYM LiveLink solve/export record.
- Added focused regression tests for the legacy COMSOL compatibility helpers and LiveLink run isolation.
- Kept the raw `comsolbatch.exe` mesh-extension failure documented as an unresolved, separate route.

The loader was tested with COMSOL 5.2a's bundled Java 8 (`1.8.0_66`), Python 3.13 x64, MPh 1.3.1, JPype 1.5.2 and MATLAB R2025b LiveLink. Newer COMSOL releases are outside this release's validation boundary.
