"""Run a real MCP compatibility matrix against COMSOL 5.2a.

This is an integration verifier. It creates disposable in-memory models and
classifies calls as successful, expected external-input cases, or failures.
On Windows with COMSOL 5.2a, prefer run_mcp_tool_matrix.ps1 so the pinned
JPype 1.5 compatibility environment is selected instead of system Python.
"""

import asyncio
import argparse
import ast
import json
import os
import sys
from pathlib import Path

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


ROOT = Path(__file__).resolve().parent.parent
EXPORT_PATH = ROOT / "comsol_models" / "matrix_heat_manual" / "matrix_export.txt"
DEFAULT_COMSOL_ROOT = Path(r"D:\Program Files\COMSOL\COMSOL52a\Multiphysics")


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--comsol-root",
        type=Path,
        default=Path(os.environ.get("COMSOL_ROOT", DEFAULT_COMSOL_ROOT)),
        help="COMSOL Multiphysics root containing bin/win64/comsolmphserver.exe",
    )
    return parser.parse_args()


def result_value(response):
    text = response.content[0].text
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        try:
            value = ast.literal_eval(text)
            return value if isinstance(value, dict) else {"success": False, "raw_response": text}
        except (SyntaxError, ValueError):
            return {"success": False, "raw_response": text}


def require_success(tool: str, value: dict) -> dict:
    if not value.get("success", "error" not in value and "raw_response" not in value):
        detail = value.get("error") or value.get("raw_response") or value
        raise RuntimeError(f"Required MCP call {tool!r} failed: {detail}")
    return value


async def run(comsol_root: Path) -> None:
    comsol_root = comsol_root.expanduser().resolve()
    server_executable = comsol_root / "bin" / "win64" / "comsolmphserver.exe"
    if not server_executable.is_file():
        raise FileNotFoundError(
            f"COMSOL root does not contain {server_executable.relative_to(comsol_root)}: "
            f"{comsol_root}"
        )

    records = []

    async def call(session, name, arguments=None):
        response = await asyncio.wait_for(session.call_tool(name, arguments or {}), timeout=90)
        value = result_value(response)
        succeeded = value.get("success", "error" not in value and "raw_response" not in value)
        records.append({"tool": name, "success": succeeded, "value": value})
        return value

    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "src.server"],
        cwd=str(ROOT),
        env={
            **os.environ,
            "COMSOL_ROOT": str(comsol_root),
            "PYTHONIOENCODING": "utf-8",
        },
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # Knowledge tools do not require a COMSOL process.
            await call(session, "docs_list")
            await call(session, "docs_get", {"topic": "workflow"})
            await call(session, "physics_get_guide", {"physics_type": "heat_transfer"})
            await call(session, "troubleshoot", {"error_type": "mesh_failed"})
            await call(session, "modeling_best_practices", {"category": "solver"})
            await call(session, "pdf_search_status")
            await call(session, "pdf_list_modules")
            await call(session, "pdf_search", {
                "query": "temperature boundary condition", "n_results": 3,
                "module": "Heat_Transfer_Module",
            })

            require_success("comsol_start", await call(session, "comsol_start", {"cores": 1}))
            await call(session, "comsol_status")

            # 2D heat-transfer model: parameters, geometry, physics, mesh, solve, results.
            heat = require_success(
                "model_create(matrix_heat)",
                await call(session, "model_create", {"name": "matrix_heat"}),
            )
            heat_name = heat["model"]["name"]
            await call(session, "model_create_component", {
                "component_name": "comp1", "space_dimension": 2, "model_name": heat_name,
            })
            await call(session, "model_list")
            await call(session, "model_set_current", {"model_name": heat_name})
            await call(session, "param_set", {"name": "L", "value": "1[m]", "description": "length", "model_name": heat_name})
            await call(session, "param_get", {"name": "L", "model_name": heat_name})
            await call(session, "param_description", {"name": "L", "text": "domain length", "model_name": heat_name})
            await call(session, "param_list", {"model_name": heat_name})
            await call(session, "geometry_create", {"geometry_name": "geom1", "space_dimension": 2, "model_name": heat_name})
            await call(session, "geometry_list", {"model_name": heat_name})
            await call(session, "geometry_add_rectangle", {
                "position": [0, 0], "size": [1, 1], "geometry_name": "geom1", "feature_name": "r1", "model_name": heat_name,
            })
            await call(session, "geometry_add_feature", {
                "feature_type": "Point", "geometry_name": "geom1", "feature_name": "pt1", "model_name": heat_name,
                "kwargs": {"p": [0.25, 0.25]},
            })
            await call(session, "geometry_add_circle", {
                "position": [0.5, 0.5], "radius": 0.2, "geometry_name": "geom1", "model_name": heat_name,
            })
            await call(session, "geometry_boolean_union", {
                "input_objects": ["r1", "c1"], "geometry_name": "geom1", "model_name": heat_name,
            })
            await call(session, "geometry_build", {"geometry_name": "geom1", "model_name": heat_name})
            await call(session, "geometry_list_features", {"geometry_name": "geom1", "model_name": heat_name})
            await call(session, "geometry_get_boundaries", {"geometry_name": "geom1", "model_name": heat_name})
            await call(session, "physics_get_available")
            heat_physics = await call(session, "physics_add_heat_transfer", {"domain_selection": "1", "model_name": heat_name})
            heat_tag = heat_physics.get("physics", {}).get("tag", "ht")
            await call(session, "physics_list", {"model_name": heat_name})
            await call(session, "physics_list_features", {"physics_name": heat_tag, "model_name": heat_name})
            await call(session, "physics_interactive_setup_heat", {"physics_name": heat_tag, "model_name": heat_name})
            await call(session, "physics_configure_boundary", {
                "physics_name": heat_tag, "boundary_condition": "Temperature", "boundary_selection": [4],
                "properties": {"T0": "305[K]"}, "model_name": heat_name,
            })
            await call(session, "physics_setup_heat_boundaries", {
                "physics_name": heat_tag, "temperature_boundaries": [1], "heat_flux_boundaries": [3],
                "temperature_value": "300[K]", "heat_flux_value": "0[W/m^2]", "model_name": heat_name,
            })
            await call(session, "physics_boundary_selection", {
                "physics_name": heat_tag, "boundary_condition_type": "Temperature", "boundary_numbers": [2],
                "properties": {"T0": "310[K]"}, "model_name": heat_name,
            })
            await call(session, "physics_set_material", {
                "physics_name": heat_tag, "material_name": "Silicon", "domain_selection": [1, 2], "model_name": heat_name,
            })
            await call(session, "mesh_create", {"mesh_name": "mesh1", "model_name": heat_name})
            await call(session, "mesh_list", {"model_name": heat_name})
            await call(session, "mesh_info", {"model_name": heat_name})
            study = await call(session, "study_create", {"study_type": "Stationary", "study_name": "std1", "model_name": heat_name})
            study_tag = study.get("study", "std1")
            await call(session, "study_list", {"model_name": heat_name})
            await call(session, "param_sweep_setup", {"parameter_name": "L", "values": ["1[m]", "2[m]"], "study_name": study_tag, "model_name": heat_name})
            await call(session, "study_solve", {"study_name": study_tag, "model_name": heat_name, "wait": True, "timeout": 90})
            await call(session, "study_solve_async", {"study_name": study_tag, "model_name": heat_name})
            await call(session, "study_get_progress")
            await call(session, "study_wait", {"timeout": 90})
            await call(session, "solutions_list", {"model_name": heat_name})
            await call(session, "datasets_list", {"model_name": heat_name})
            await call(session, "results_evaluate", {"expression": "T", "model_name": heat_name})
            await call(session, "results_global_evaluate", {"expression": "T", "model_name": heat_name})
            await call(session, "results_inner_values", {"model_name": heat_name})
            await call(session, "results_outer_values", {"model_name": heat_name})
            await call(session, "results_exports_list", {"model_name": heat_name})
            await call(session, "results_plots_list", {"model_name": heat_name})
            await call(session, "results_export_data", {"file_path": str(EXPORT_PATH), "model_name": heat_name})
            await call(session, "model_inspect", {"model_name": heat_name})
            saved = ROOT / "comsol_models" / "matrix_heat_manual" / "matrix_saved.mph"
            await call(session, "model_save", {"model_name": heat_name, "file_path": str(saved)})
            loaded = await call(session, "model_load", {"file_path": str(saved), "set_current": False})
            if loaded.get("success"):
                await call(session, "model_remove", {"model_name": loaded["model"]["name"]})
            await call(session, "model_save_version", {"model_name": heat_name, "description": "matrix validation"})
            clone = await call(session, "model_clone", {"model_name": heat_name, "new_name": "matrix_heat_clone", "set_current": False})
            if clone.get("success"):
                await call(session, "model_remove", {"model_name": "matrix_heat_clone"})

            # 3D geometry and physics interfaces exercise the remaining primitives and couplings.
            three_d = require_success(
                "model_create(matrix_3d)",
                await call(session, "model_create", {"name": "matrix_3d"}),
            )
            three_name = three_d["model"]["name"]
            await call(session, "geometry_create", {"geometry_name": "geom1", "space_dimension": 3, "model_name": three_name})
            await call(session, "geometry_add_block", {"position": [0, 0, 0], "size": [1, 1, 1], "geometry_name": "geom1", "feature_name": "blk1", "model_name": three_name})
            await call(session, "geometry_add_cylinder", {"position": [0.5, 0.5, 0], "radius": 0.2, "height": 1, "geometry_name": "geom1", "feature_name": "cyl1", "model_name": three_name})
            await call(session, "geometry_add_sphere", {"position": [0.5, 0.5, 0.5], "radius": 0.15, "geometry_name": "geom1", "feature_name": "sph1", "model_name": three_name})
            await call(session, "geometry_boolean_difference", {"input_object": "blk1", "objects_to_subtract": ["sph1"], "geometry_name": "geom1", "feature_name": "dif1", "model_name": three_name})
            await call(session, "geometry_build", {"geometry_name": "geom1", "model_name": three_name})
            electro = await call(session, "physics_add_electrostatics", {"domain_selection": "1", "model_name": three_name})
            solid = await call(session, "physics_add_solid_mechanics", {"domain_selection": "1", "model_name": three_name})
            electro_tag = electro.get("physics", {}).get("tag", "es")
            solid_tag = solid.get("physics", {}).get("tag", "solid")
            await call(session, "multiphysics_add", {"coupling_type": "ThermalStress", "physics_list": [electro_tag, solid_tag], "model_name": three_name})
            await call(session, "physics_remove", {"physics_name": electro_tag, "model_name": three_name})

            # Separate flow model, because its boundary-condition setup needs a flow interface.
            flow = require_success(
                "model_create(matrix_flow)",
                await call(session, "model_create", {"name": "matrix_flow"}),
            )
            flow_name = flow["model"]["name"]
            await call(session, "geometry_create", {"geometry_name": "geom1", "space_dimension": 2, "model_name": flow_name})
            await call(session, "geometry_add_rectangle", {"position": [0, 0], "size": [2, 1], "geometry_name": "geom1", "model_name": flow_name})
            await call(session, "geometry_build", {"geometry_name": "geom1", "model_name": flow_name})
            flow_physics = await call(session, "physics_add_laminar_flow", {"domain_selection": "1", "model_name": flow_name})
            flow_tag = flow_physics.get("physics", {}).get("tag", "spf")
            await call(session, "physics_setup_flow_boundaries", {"physics_name": flow_tag, "inlet_boundaries": [1], "outlet_boundaries": [3], "inlet_velocity": "1[m/s]", "model_name": flow_name})
            await call(session, "physics_interactive_setup_flow", {"physics_name": flow_tag, "model_name": flow_name})

            await call(session, "comsol_status")
            await call(session, "comsol_disconnect")

    succeeded = [record for record in records if record["success"]]
    failed = [record for record in records if not record["success"]]
    print(json.dumps({
        "total": len(records),
        "succeeded": len(succeeded),
        "failed": len(failed),
        "failed_tools": [{"tool": item["tool"], "error": item["value"].get("error") or item["value"].get("raw_response")} for item in failed],
        "export_bytes": EXPORT_PATH.stat().st_size if EXPORT_PATH.is_file() else 0,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    arguments = parse_args()
    asyncio.run(run(arguments.comsol_root))
