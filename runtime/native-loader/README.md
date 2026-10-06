# COMSOL 5.2a native loader

This directory contains the process-level native loader used by the local
COMSOL 5.2a LiveLink/MCP route. It is kept under the repository runtime tree
so the persistent loader is stored on `D:` with the rest of the COMSOL MCP
runtime.

- `dllpath-rust-agent.dll`: verified Java `-agentpath` loader.
- `dllpath-rust-agent.rs`: source used to build the loader.
- SHA-256 of the verified DLL built from the checked-in source: `51133AF7356A69AE2618A9DDAC961685B699DDD65CD3D8F90685A9622CBB2D8D`

The loader is enabled only through the `JAVA_TOOL_OPTIONS` value of the
Codex `COMSOL_LiveLink` MCP process. It does not modify system `PATH`, the
COMSOL installation, the registry, or MATLAB user configuration.
