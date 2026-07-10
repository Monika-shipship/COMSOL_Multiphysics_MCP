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


def test_geometry_entity_counts_uses_comsol_52a_method_names():
    from src.comsol_compat import geometry_entity_counts

    class Geometry:
        def getNBoundaries(self):
            return 4

        def getNDomains(self):
            return 1

    assert geometry_entity_counts(Geometry()) == (4, 1)


def test_create_physics_interface_binds_geometry_for_legacy_model():
    from src.comsol_compat import create_physics_interface

    class PhysicsList:
        def __init__(self):
            self.calls = []

        def create(self, *args):
            self.calls.append(args)
            return "physics"

    class LegacyModel:
        def __init__(self):
            self.physics_list = PhysicsList()

        def physics(self):
            return self.physics_list

    model = LegacyModel()
    assert create_physics_interface(model, "ht", "HeatTransfer", "geom1") == "physics"
    assert model.physics_list.calls == [("ht", "HeatTransfer", "geom1")]


def test_find_physics_java_supports_tag_indexed_legacy_lists():
    from src.tools.physics import _find_physics_java

    class Physics:
        def __init__(self, tag, label):
            self._tag = tag
            self._label = label

        def tag(self):
            return self._tag

        def label(self):
            return self._label

    class PhysicsList:
        def __init__(self):
            self.items = {"ht": Physics("ht", "Heat Transfer")}

        def tags(self):
            return list(self.items)

        def get(self, tag):
            return self.items[tag]

    class LegacyModel:
        def __init__(self):
            self._physics = PhysicsList()

        def physics(self):
            return self._physics

    assert _find_physics_java(LegacyModel(), "ht").tag() == "ht"
    assert _find_physics_java(LegacyModel(), "Heat Transfer").tag() == "ht"


def test_create_legacy_mesh_creates_and_runs_automatic_mesh():
    from src.tools.mesh import _create_legacy_mesh

    class Mesh:
        def __init__(self):
            self.automatic_value = None
            self.ran = False

        def automatic(self, value):
            self.automatic_value = value

        def run(self):
            self.ran = True

    class MeshList:
        def __init__(self):
            self.calls = []
            self.mesh = Mesh()

        def create(self, *args):
            self.calls.append(args)
            return self.mesh

    class LegacyModel:
        def __init__(self):
            self.mesh_list = MeshList()

        def mesh(self):
            return self.mesh_list

    model = LegacyModel()
    mesh = _create_legacy_mesh(model, "mesh1", "geom1")
    assert mesh is model.mesh_list.mesh
    assert model.mesh_list.calls == [("mesh1", "geom1")]
    assert mesh.automatic_value is True
    assert mesh.ran is True


def test_create_legacy_study_step_uses_feature_list():
    from src.tools.study import _create_study_step

    class Features:
        def __init__(self):
            self.calls = []

        def create(self, *args):
            self.calls.append(args)

    class Study:
        def __init__(self):
            self.features = Features()

        def feature(self):
            return self.features

    study = Study()
    _create_study_step(study, "step1", "stat", legacy=True)
    assert study.features.calls == [("step1", "Stationary")]


def test_set_material_properties_writes_values_to_default_group():
    from src.tools.physics import _set_material_properties

    class PropertyGroup:
        def __init__(self):
            self.calls = []

        def set(self, name, value):
            self.calls.append((name, value))

    class Material:
        def __init__(self):
            self.group = PropertyGroup()

        def propertyGroup(self, name):
            assert name == "def"
            return self.group

    material = Material()
    applied = _set_material_properties(material, {"thermalconductivity": "1[W/(m*K)]"})

    assert applied == {"thermalconductivity": "1[W/(m*K)]"}
    assert material.group.calls == [("thermalconductivity", ["1[W/(m*K)]"])]


def test_create_legacy_boundary_feature_uses_boundary_api_and_dimension():
    from src.tools.physics import _create_boundary_feature

    class Features:
        def __init__(self):
            self.calls = []

        def create(self, *args):
            self.calls.append(args)
            return "boundary"

    class Physics:
        def __init__(self):
            self.features = Features()

        def feature(self):
            return self.features

    class Geometry:
        def getSDim(self):
            return 2

    physics = Physics()
    assert _create_boundary_feature(physics, Geometry(), "temp1", "Temperature", legacy=True) == "boundary"
    assert physics.features.calls == [("temp1", "TemperatureBoundary", 1)]


def test_solve_legacy_study_runs_java_study_tag():
    from src.tools.study import _solve_legacy_study

    class Study:
        def __init__(self):
            self.ran = False

        def run(self):
            self.ran = True

    class Studies:
        def __init__(self):
            self.study = Study()
            self.requested_tag = None

        def __call__(self, tag):
            self.requested_tag = tag
            return self.study

    class Model:
        def __init__(self):
            self.studies = Studies()

        def study(self, tag):
            return self.studies(tag)

    model = Model()
    _solve_legacy_study(model, "std1")
    assert model.studies.requested_tag == "std1"
    assert model.studies.study.ran is True


def test_async_solver_uses_supplied_solve_callable():
    from src.async_handler.solver import AsyncSolver, SolverStatus

    class Model:
        def name(self):
            return "async-model"

        def solve(self, _study_name):
            raise AssertionError("The model solve method should not be called.")

    calls = []
    solver = AsyncSolver()
    assert solver.start_solve(Model(), "std1", solve_callable=lambda: calls.append("solved"))
    assert solver.wait(timeout=5)
    assert calls == ["solved"]
    assert solver.progress.status is SolverStatus.COMPLETED


def test_next_geometry_feature_tag_uses_java_tags():
    from src.tools.geometry import _next_feature_tag

    class Features:
        def tags(self):
            return ["r1", "r2"]

    assert _next_feature_tag(Features(), "r") == "r3"
