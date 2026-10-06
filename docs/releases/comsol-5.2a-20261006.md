# COMSOL 5.2a native startup repair

This release is for COMSOL Multiphysics 5.2a, file version 5.2.1.152, on Windows x64.

It fixes the Java native startup path that produced `csutil.dll: Can't find dependent libraries` and the follow-on `FlLicense` class error. The repository now includes a process-local loader, the `COMSOL_LiveLink` stdio entrypoint, D-drive runtime setup, MCP smoke verification, and protected-copy EYM solve/export tooling.

Validated on the local machine with COMSOL's Java 8 (`1.8.0_66`), Python 3.13 x64, MPh 1.3.1, JPype 1.5.2 and MATLAB R2025b LiveLink. The smoke test returned midpoint `50.0000000000001` and maximum absolute error `7.1e-13`. The protected EYM copy solved through LiveLink and produced a 2,885,304-byte MPH plus a 1001-point profile CSV. The source MPH was unchanged.

The raw `comsolbatch.exe` route remains documented as a separate failure at mesh extension. This release does not claim that route succeeded. COMSOL 5.6 and 6.x are outside this release's validation scope.

## Asset

`dllpath-rust-agent.dll` is the Windows x64 loader built from `runtime/native-loader/dllpath-rust-agent.rs`.

SHA-256: `51133AF7356A69AE2618A9DDAC961685B699DDD65CD3D8F90685A9622CBB2D8D`
