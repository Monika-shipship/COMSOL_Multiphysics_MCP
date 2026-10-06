# COMSOL 5.2a startup diagnosis

The machine had COMSOL Multiphysics 5.2a (`5.2.1.152`) installed at `D:\Program Files\COMSOL\COMSOL52a\Multiphysics`. The batch and LiveLink failures reported `csutil.dll: Can't find dependent libraries`; Java then surfaced `NoClassDefFoundError: com/comsol/nativejni/util/FlLicense`.

The files were present. The failure came from the native DLL search context used by the Java startup path. `csutil.dll` depends on COMSOL native libraries, Intel OpenMP and the Visual C++ runtime. Loading the files with Python `ctypes` alone did not reproduce the Java chain.

`runtime/native-loader/dllpath-rust-agent.dll` is a Java `-agentpath` library. At `Agent_OnLoad` it reads the absolute `COMSOL_ROOT`, registers COMSOL's `bin\win64`, `lib\win64`, graphics and CAD-import directories, and preloads the native chain with `LoadLibraryExW`. It reports a Windows error code for a failed load when `COMSOL_NATIVE_TRACE=1` is set. The loader is process-local. It does not copy or replace COMSOL DLLs and does not alter system PATH or the registry.

The launcher in `scripts/start_comsol52a.py` supplies the agent only to the MCP process and its children. The current machine registration uses the D-drive checkout:

```text
D:\Repos\AIwork\Codex-plugins\COMSOL_Multiphysics_MCP\runtime\python52a\Scripts\python.exe
D:\Repos\AIwork\Codex-plugins\COMSOL_Multiphysics_MCP\scripts\start_comsol52a.py
D:\Repos\AIwork\Codex-plugins\COMSOL_Multiphysics_MCP\runtime\native-loader\dllpath-rust-agent.dll
```

## Evidence

The repository verifier used the real MCP stdio protocol and checked each route's return value, logs, output files, process list and port 2036 state.

| Route | Result |
| --- | --- |
| `status` | COMSOL server, MATLAB and LiveLink paths exist; no stale process or port was assumed. |
| `start_server` | COMSOL 5.2a server started and listened on 2036. |
| `smoke_test` | MATLAB LiveLink returned 0; midpoint `50.0000000000001`; maximum absolute error `7.1e-13`; MPH/CSV/JSON outputs were nonempty. |
| EYM protected-copy solve | LiveLink returned 0; solved MPH was 2,885,304 bytes; 1001-point profile CSV and summary were written. |
| cleanup | The verifier stopped the server it started; COMSOL, MATLAB and Java processes and port 2036 were absent afterward. |

The source model `D:\Repos\PaperWork\3\爱因斯坦-杨-米尔斯-Mywork\before\sources\E-YM.mph` was not changed. Its SHA-256 and the protected input copy are both `5546CD0BD3F05A3619D93990DC6348FC275C482FB6B017C4FAE0D920F5DBD5FF`.

The direct `comsolbatch.exe` route remains separate. During the investigation it reached the 5% mesh-extension stage and failed to produce an output MPH. A zero launcher exit code or a listening port is therefore not treated as a solve result.

## Rollback

Remove the `COMSOL_LiveLink` registration and the repository runtime directory after stopping its processes. The COMSOL installation, system PATH, registry, MATLAB user configuration and source MPH require no rollback.
