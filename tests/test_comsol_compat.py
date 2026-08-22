import os
from pathlib import Path

import pytest


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


def test_create_legacy_generic_feature_uses_tag_type_order_and_properties():
    from src.tools.geometry import _create_legacy_generic_feature

    class Feature:
        def __init__(self):
            self.values = []

        def set(self, name, value):
            self.values.append((name, value))

    class Features:
        def __init__(self):
            self.calls = []
            self.feature = Feature()

        def tags(self):
            return ["pt1"]

        def create(self, *args):
            self.calls.append(args)
            return self.feature

    class Geometry:
        def __init__(self):
            self.features = Features()

        def feature(self):
            return self.features

    geometry = Geometry()
    assert _create_legacy_generic_feature(geometry, "Point", None, {"p": ["0", "1"]}) == "pt2"
    assert geometry.features.calls == [("pt2", "Point")]
    assert geometry.features.feature.values == [("p", ["0", "1"])]


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


def test_create_generic_boundary_feature_uses_legacy_temperature_mapping():
    from src.tools.physics import _create_generic_boundary_feature

    class Geometry:
        def getSDim(self):
            return 2

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

    class Geometries:
        def tags(self):
            return ["geom1"]

    class Model:
        def geom(self, name=None):
            return Geometries() if name is None else Geometry()

    physics = Physics()
    assert _create_generic_boundary_feature(Model(), physics, "bc1", "Temperature") == "boundary"
    assert physics.features.calls == [("bc1", "TemperatureBoundary", 1)]


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


def test_next_geometry_feature_tag_ignores_unrelated_automatic_features():
    from src.tools.geometry import _next_feature_tag

    class Features:
        def tags(self):
            return ["fin"]

    assert _next_feature_tag(Features(), "blk") == "blk1"


def test_next_geometry_feature_tag_converts_java_string_like_tags():
    from src.tools.geometry import _next_feature_tag

    class JavaString:
        def __str__(self):
            return "blk2"

    class Features:
        def tags(self):
            return [JavaString()]

    assert _next_feature_tag(Features(), "blk") == "blk3"


def test_physics_feature_info_uses_legacy_feature_tags():
    from src.tools.physics import _physics_feature_info

    class Feature:
        def __init__(self, label):
            self._label = label

        def label(self):
            return self._label

    class Features:
        def tags(self):
            return ["temp1", "temp2"]

        def get(self, tag):
            return Feature(f"Label {tag}")

    assert _physics_feature_info(Features()) == [
        {"name": "temp1", "label": "Label temp1"},
        {"name": "temp2", "label": "Label temp2"},
    ]


def test_resolve_legacy_multiphysics_maps_thermal_stress_to_expansion():
    from src.tools.physics import _resolve_legacy_multiphysics

    class Geometry:
        def getSDim(self):
            return 3

    assert _resolve_legacy_multiphysics("ThermalStress", "geom1", Geometry()) == (
        "ThermalExpansion",
        "geom1",
        3,
    )


def test_resolve_results_dataset_uses_first_available_dataset():
    from src.tools.results import _resolve_dataset

    class Model:
        def datasets(self):
            return ["Dataset 1"]

    assert _resolve_dataset(Model(), None) == "Dataset 1"
    assert _resolve_dataset(Model(), "custom") == "custom"


def test_resolve_results_dataset_keeps_mph_dataset_label_for_legacy_model():
    from src.tools.results import _resolve_dataset

    class Datasets:
        def tags(self):
            return ["dset1"]

    class Results:
        def dataset(self):
            return Datasets()

    class JavaModel:
        def result(self):
            return Results()

    class Model:
        java = JavaModel()

        def datasets(self):
            return ["Study 1//Solution 1"]

    assert _resolve_dataset(Model(), None) == "Study 1//Solution 1"


def test_legacy_export_dataset_uses_java_dataset_tag():
    from src.tools.results import _legacy_export_dataset

    class Datasets:
        def tags(self):
            return ["dset1"]

    class Results:
        def dataset(self):
            return Datasets()

    class JavaModel:
        def result(self):
            return Results()

    class Model:
        java = JavaModel()

    assert _legacy_export_dataset(Model()) == "dset1"


def test_legacy_model_inspection_reads_top_level_java_tags():
    from src.tools.model import _legacy_model_structure

    class List:
        def __init__(self, tags):
            self._tags = tags

        def tags(self):
            return self._tags

    class JavaModel:
        def geom(self):
            return List(["geom1"])

        def physics(self):
            return List(["ht"])

        def material(self):
            return List(["mat1"])

        def mesh(self):
            return List(["mesh1"])

        def study(self):
            return List(["std1"])

        def sol(self):
            return List(["sol1"])

        def result(self):
            return List(["pg1"])

        def multiphysics(self):
            return List(["te1"])

    structure = _legacy_model_structure(JavaModel())
    assert structure["components"] == ["comp1"]
    assert structure["geometries"] == ["geom1"]
    assert structure["physics"] == ["ht"]
    assert structure["studies"] == ["std1"]


def test_clone_legacy_model_saves_source_then_restores_its_label():
    from src.tools.model import _clone_legacy_java_model

    class JavaModel:
        def __init__(self):
            self.saved_path = None
            self.label_value = None

        def save(self, path):
            self.saved_path = path

        def label(self, value):
            self.label_value = value

    java_model = JavaModel()
    loaded = []
    clone = _clone_legacy_java_model(
        java_model,
        "source",
        "clone",
        "C:/tmp/source.mph",
        lambda name, path: loaded.append((name, path)) or "clone-java",
    )

    assert clone == "clone-java"
    assert java_model.saved_path == "C:/tmp/source.mph"
    assert java_model.label_value == "source"
    assert loaded == [("clone", "C:/tmp/source.mph")]


def test_legacy_model_parameters_use_top_level_param_api():
    from src.tools.model import _legacy_model_parameters

    class Params:
        def varnames(self):
            return ["L"]

        def get(self, name):
            assert name == "L"
            return "1[m]"

        def descr(self, name):
            assert name == "L"
            return "Length"

    class JavaModel:
        def param(self):
            return Params()

    assert _legacy_model_parameters(JavaModel()) == {
        "L": {"value": "1[m]", "description": "Length"}
    }


def test_create_legacy_circle_feature_uses_java_geometry_features():
    from src.tools.geometry import _create_legacy_circle

    class Circle:
        def __init__(self):
            self.properties = []

        def set(self, name, value):
            self.properties.append((name, value))

    class Features:
        def __init__(self):
            self.circle = Circle()
            self.calls = []

        def tags(self):
            return ["fin"]

        def create(self, *args):
            self.calls.append(args)
            return self.circle

    class Geometry:
        def __init__(self):
            self.features = Features()

        def feature(self):
            return self.features

    geometry = Geometry()
    assert _create_legacy_circle(geometry, [0.5, 0.5], 0.2) == "c1"
    assert geometry.features.calls == [("c1", "Circle")]
    assert geometry.features.circle.properties == [("pos", ["0.5", "0.5"]), ("r", "0.2")]


def test_create_legacy_union_feature_selects_input_tags():
    from src.tools.geometry import _create_legacy_union

    class Selection:
        def __init__(self):
            self.value = None

        def set(self, value):
            self.value = value

    class Union:
        def __init__(self):
            self.input = Selection()

        def selection(self, name):
            assert name == "input"
            return self.input

    class Features:
        def __init__(self):
            self.union = Union()

        def tags(self):
            return ["r1", "c1"]

        def create(self, tag, feature_type):
            assert (tag, feature_type) == ("uni1", "Union")
            return self.union

    class Geometry:
        def __init__(self):
            self.features = Features()

        def feature(self):
            return self.features

    geometry = Geometry()
    assert _create_legacy_union(geometry, ["r1", "c1"]) == "uni1"
    assert geometry.features.union.input.value == ["r1", "c1"]


def test_legacy_inlet_property_uses_comsol_52a_name():
    from src.tools.physics import _boundary_property_name

    assert _boundary_property_name("Inlet", "U0", legacy=True) == "U0in"
    assert _boundary_property_name("Outlet", "p0", legacy=True) == "p0"


def test_create_legacy_parametric_sweep_uses_study_feature_api():
    from src.tools.parameters import _create_legacy_parametric_sweep

    class Sweep:
        def __init__(self):
            self.values = []

        def set(self, name, value):
            self.values.append((name, value))

    class Features:
        def __init__(self):
            self.sweep = Sweep()
            self.calls = []

        def create(self, *args):
            self.calls.append(args)
            return self.sweep

    class Study:
        def __init__(self):
            self.features = Features()

        def feature(self):
            return self.features

    study = Study()
    assert _create_legacy_parametric_sweep(study, "param", "a", ["1", "2"]) == "param"
    assert study.features.calls == [("param", "Parametric")]
    assert study.features.sweep.values == [("pname", ["a"]), ("plist", ["1", "2"])]


def test_local_pdf_search_returns_ranked_matching_pages(monkeypatch, tmp_path: Path):
    from src.knowledge import embedded

    class FakeProcessor:
        def __init__(self, _pdf_dir):
            pass

        def get_pdf_files(self):
            return [
                tmp_path / "Heat_Transfer_Module" / "guide.pdf",
                tmp_path / "CFD_Module" / "guide.pdf",
            ]

        def get_module_name(self, pdf_path):
            return pdf_path.parent.name

        def extract_text_from_pdf(self, pdf_path):
            if pdf_path.parent.name == "Heat_Transfer_Module":
                return [(7, "Temperature boundary condition sets the heat transfer temperature.")]
            return [(2, "Velocity inlet and pressure outlet are fluid flow conditions.")]

        def clean_text(self, text):
            return text

    monkeypatch.setattr(embedded, "PDFProcessor", FakeProcessor, raising=False)
    monkeypatch.setattr(embedded, "DEFAULT_PDF_DIR", tmp_path, raising=False)

    results = embedded._local_pdf_search("temperature boundary", 3)

    assert len(results) == 1
    assert results[0]["module"] == "Heat_Transfer_Module"
    assert results[0]["page"] == 7
    assert results[0]["score"] > 0


def test_create_legacy_data_export_configures_dataset_and_filename():
    from src.tools.results import _create_legacy_data_export

    class ExportNode:
        def __init__(self):
            self.values = []

        def set(self, name, value):
            self.values.append((name, value))

    class Exports:
        def __init__(self):
            self.calls = []
            self.node = ExportNode()

        def create(self, *args):
            self.calls.append(args)
            return self.node

    exports = Exports()
    node = _create_legacy_data_export(exports, "data1", "dset1", "C:/tmp/result.txt")

    assert node is exports.node
    assert exports.calls == [("data1", "Data")]
    assert exports.node.values == [("data", "dset1"), ("filename", "C:/tmp/result.txt")]


def test_local_pdf_files_prioritizes_postprocessing_manual_for_export_queries(monkeypatch, tmp_path: Path):
    from src.knowledge import embedded

    class FakeProcessor:
        def get_pdf_files(self):
            return [
                tmp_path / "COMSOL_Multiphysics" / "COMSOL_ReferenceManual.pdf",
                tmp_path / "COMSOL_Multiphysics" / "COMSOL_PostprocessingAndVisualization.pdf",
                tmp_path / "COMSOL_Multiphysics" / "COMSOL_ProgrammingReferenceManual.pdf",
            ]

        def get_module_name(self, _pdf_path):
            return "COMSOL_Multiphysics"

    files = embedded._local_pdf_files(FakeProcessor(), "image export plot", None)

    assert files[0].name == "COMSOL_PostprocessingAndVisualization.pdf"


def test_pdf_search_dependency_probe_does_not_import_embedding_modules(monkeypatch):
    from src.knowledge import embedded

    requested = []

    def find_spec(name):
        requested.append(name)
        return object() if name == "fitz" else None

    monkeypatch.setattr(embedded.importlib.util, "find_spec", find_spec)

    assert embedded._pdf_search_ready() is True
    assert requested == ["fitz"]


def test_mcp_tool_matrix_required_calls_fail_fast_with_the_tool_error():
    from scripts.run_mcp_tool_matrix import require_success

    value = {"success": True, "model": {"name": "matrix_heat"}}
    assert require_success("model_create", value) is value

    with pytest.raises(RuntimeError, match="comsol_start.*installation not found"):
        require_success(
            "comsol_start",
            {"success": False, "error": "installation not found"},
        )
