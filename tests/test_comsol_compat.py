import os
from pathlib import Path


def test_build_legacy_backend_from_comsol_root(tmp_path: Path):
    from src.comsol_compat import build_legacy_backend

    root = tmp_path / "COMSOL52a" / "Multiphysics"
    backend = build_legacy_backend(root, "COMSOL Multiphysics 5.2.1.152")

    assert backend is not None
    assert backend["name"] == "5.2a"
    assert backend["major"] == 5
    assert backend["minor"] == 2
    assert backend["patch"] == 1
    assert backend["build"] == 152
    assert backend["root"] == root
    assert backend["jvm"] == root / "java" / "win64" / "jre" / "bin" / "server" / "jvm.dll"
    assert backend["server"] == [root / "bin" / "win64" / "comsolmphserver.exe"]


def test_component_container_uses_model_for_legacy_comsol():
    from src.comsol_compat import component_container

    class LegacyModel:
        pass

    model = LegacyModel()
    assert component_container(model, "comp1") is model


def test_prepare_legacy_environment_adds_comsol_native_library_paths(monkeypatch, tmp_path: Path):
    from src.comsol_compat import prepare_legacy_environment

    root = tmp_path / "Multiphysics"
    monkeypatch.setenv("PATH", "existing")

    prepare_legacy_environment(root)

    path_parts = os.environ["PATH"].split(";")
    assert str(root / "bin" / "win64") in path_parts
    assert str(root / "lib" / "win64") in path_parts
    assert str(root / "ext" / "cadimport" / "win64") in path_parts
    assert "existing" in path_parts


def test_geometry_feature_creation_omits_none_feature_name():
    from src.tools.geometry import _create_geometry_feature

    class FeatureList:
        def __init__(self):
            self.calls = []

        def create(self, *args):
            self.calls.append(args)
            return "feature"

    features = FeatureList()
    assert _create_geometry_feature(features, "Interval", None) == "feature"
    assert features.calls == [("Interval",)]


def test_geometry_feature_properties_accept_nested_kwargs():
    from src.tools.geometry import _geometry_feature_properties

    assert _geometry_feature_properties({"kwargs": {"p1": "0", "p2": "1"}}) == {
        "p1": "0",
        "p2": "1",
    }


def test_resolve_geometry_name_maps_comsol_tag_to_localized_label():
    from src.tools.geometry import _resolve_geometry_name

    class Geometry:
        def tag(self):
            return "geom1"

        def label(self):
            return "Geometry 1"

    assert _resolve_geometry_name(["Geometry 1"], [Geometry()], "geom1") == "Geometry 1"
