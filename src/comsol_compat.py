"""Compatibility helpers for older COMSOL installations."""

from __future__ import annotations

import os
import platform
import subprocess
from functools import lru_cache
from pathlib import Path
from typing import Any

import mph.discovery as discovery


_compatibility_enabled = False
_dll_directory_handles: list[Any] = []


def component_container(model_java: Any, component_name: str = "comp1") -> Any:
    """Return a component or the model itself for pre-component COMSOL APIs."""
    try:
        return model_java.component(component_name)
    except AttributeError:
        return model_java


def component_containers(model_java: Any) -> list[Any]:
    """Return all component containers, including a legacy model container."""
    try:
        components = model_java.component()
    except AttributeError:
        return [model_java]
    return [components.get(index) for index in range(components.size())]


def prepare_legacy_environment(root: Path) -> None:
    """Make COMSOL's native libraries visible to the current process."""
    architecture = discovery.detect_architecture()
    native_paths = [root / "bin" / architecture, root / "lib" / architecture]
    if platform.system() == "Windows":
        native_paths.append(root / "ext" / "cadimport" / architecture)
        bundled_runtime = Path(
            os.environ.get(
                "COMSOL_MCP_RUNTIME",
                Path(__file__).resolve().parent.parent / "runtime" / "vc2012",
            )
        )
        if bundled_runtime.is_dir():
            native_paths.insert(0, bundled_runtime)

    existing = os.environ.get("PATH", "").split(os.pathsep)
    prefix = [str(path) for path in native_paths if str(path) not in existing]
    if prefix:
        os.environ["PATH"] = os.pathsep.join(prefix + existing)
    if hasattr(os, "add_dll_directory"):
        for path in native_paths:
            if path.is_dir():
                _dll_directory_handles.append(os.add_dll_directory(str(path)))


def build_legacy_backend(root: Path, version_output: str) -> dict[str, Any] | None:
    """Build an MPh backend description from an older COMSOL installation."""
    try:
        name, major, minor, patch, build = discovery.parse(version_output)
        architecture = discovery.detect_architecture()
    except (OSError, ValueError):
        return None

    if platform.system() == "Windows":
        server = root / "bin" / architecture / "comsolmphserver.exe"
        jvm = root / "java" / architecture / "jre" / "bin" / "server" / "jvm.dll"
        server_command: list[Path | str] = [server]
    else:
        server = root / "bin" / architecture / "comsol"
        jvm = root / "java" / architecture / "jre" / "lib" / "amd64" / "server" / "libjvm.so"
        server_command = [server, "mphserver"]

    return {
        "name": name,
        "major": major,
        "minor": minor,
        "patch": patch,
        "build": build,
        "root": root,
        "jvm": jvm,
        "server": server_command,
    }


def _configured_legacy_backend() -> dict[str, Any] | None:
    configured_root = os.environ.get("COMSOL_ROOT")
    if not configured_root:
        return None

    root = Path(configured_root).expanduser()
    architecture = discovery.detect_architecture()
    if platform.system() == "Windows":
        server = root / "bin" / architecture / "comsolmphserver.exe"
    else:
        server = root / "bin" / architecture / "comsol"
    if not server.is_file():
        return None

    try:
        process = subprocess.run(
            [server, "--version"],
            check=True,
            timeout=15,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="ascii",
            errors="ignore",
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None

    backend = build_legacy_backend(root, process.stdout.strip())
    if backend is None or not Path(backend["jvm"]).is_file():
        return None
    return backend


def enable_mph_legacy_discovery() -> None:
    """Add an explicit COMSOL_ROOT fallback to MPh discovery."""
    global _compatibility_enabled
    if _compatibility_enabled:
        return

    configured_root = os.environ.get("COMSOL_ROOT")
    if configured_root:
        prepare_legacy_environment(Path(configured_root).expanduser())

    original_find_backends = discovery.find_backends

    @lru_cache(maxsize=1)
    def find_backends_with_legacy_fallback():
        backends = list(original_find_backends())
        fallback = _configured_legacy_backend()
        if fallback and fallback["name"] not in {item["name"] for item in backends}:
            backends.append(fallback)
        return backends

    discovery.find_backends = find_backends_with_legacy_fallback
    _compatibility_enabled = True
