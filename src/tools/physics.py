"""Physics tools for COMSOL MCP Server."""

from typing import Optional, Sequence
from mcp.server.fastmcp import FastMCP

from ..comsol_compat import (
    component_container,
    component_containers,
    create_physics_interface,
    first_geometry_tag,
    geometry_entity_counts,
    is_legacy_model,
)
from .session import session_manager

_tag_counter = {}


THERMAL_MATERIAL_PROPERTIES = {
    "silicon": {
        "thermalconductivity": "130[W/(m*K)]",
        "density": "2330[kg/m^3]",
        "heatcapacity": "700[J/(kg*K)]",
    },
    "copper": {
        "thermalconductivity": "400[W/(m*K)]",
        "density": "8960[kg/m^3]",
        "heatcapacity": "385[J/(kg*K)]",
    },
    "water": {
        "thermalconductivity": "0.6[W/(m*K)]",
        "density": "1000[kg/m^3]",
        "heatcapacity": "4180[J/(kg*K)]",
    },
    "air": {
        "thermalconductivity": "0.026[W/(m*K)]",
        "density": "1.2[kg/m^3]",
        "heatcapacity": "1005[J/(kg*K)]",
    },
}


def _set_material_properties(material, properties: dict[str, str]) -> dict[str, str]:
    """Write scalar material properties to COMSOL's default property group."""
    group = material.propertyGroup("def")
    for name, value in properties.items():
        group.set(name, [value])
    return properties.copy()


BOUNDARY_FEATURE_TYPES = {
    "Temperature": "TemperatureBoundary",
    "HeatFlux": "HeatFluxBoundary",
    "ElectricPotential": "ElectricPotentialBoundary",
    "SurfaceChargeDensity": "SurfaceChargeDensity",
    "Inlet": "InletBoundary",
    "Outlet": "OutletBoundary",
}


def _create_boundary_feature(physics, geometry, tag: str, boundary_condition: str, legacy: bool):
    """Create a boundary condition using the physics API for the active COMSOL generation."""
    feature_type = BOUNDARY_FEATURE_TYPES.get(boundary_condition, boundary_condition)
    if legacy:
        boundary_dimension = int(geometry.getSDim()) - 1
        return physics.feature().create(tag, feature_type, boundary_dimension)
    return physics.create(tag, feature_type)


def _boundary_property_name(boundary_condition: str, property_name: str, legacy: bool) -> str:
    """Map boundary properties whose COMSOL 5.2a names differ from newer APIs."""
    if legacy and boundary_condition == "Inlet" and property_name == "U0":
        return "U0in"
    return property_name


def _physics_feature_info(features) -> list[dict[str, str]]:
    """Return feature tags and labels from the Java feature list."""
    result = []
    for tag in features.tags():
        feature = features.get(tag)
        result.append({"name": tag, "label": feature.label()})
    return result


def _resolve_legacy_multiphysics(coupling_type: str, geometry_tag: str, geometry) -> tuple[str, str, int]:
    """Map MCP-friendly coupling names to COMSOL 5.2a Java API names."""
    coupling_names = {
        "ThermalStress": "ThermalExpansion",
    }
    return coupling_names.get(coupling_type, coupling_type), geometry_tag, int(geometry.getSDim())


def _find_physics_java(jm, physics_name):
    """Look up a physics node by label or tag across all components."""
    for comp in component_containers(jm):
        physics_list = comp.physics()
        try:
            tags = list(physics_list.tags())
        except (AttributeError, TypeError):
            tags = list(range(physics_list.size()))
        for tag in tags:
            p = physics_list.get(tag)
            if p.label() == physics_name or p.tag() == physics_name:
                return p
    return None


def _make_tag(prefix="bc"):
    """Generate a unique tag using a monotonic counter."""
    _tag_counter[prefix] = _tag_counter.get(prefix, 0) + 1
    return f"{prefix}_{_tag_counter[prefix]}"


PHYSICS_INTERFACES = {
    "AC/DC": {
        "electrostatic": "Electrostatics (es)",
        "electric_currents": "Electric Currents (ec)",
        "magnetic_fields": "Magnetic Fields (mf)",
        "electromagnetic_waves": "Electromagnetic Waves (emw)",
    },
    "Structural": {
        "solid_mechanics": "Solid Mechanics (solid)",
        "shell": "Shell (shell)",
        "beam": "Beam (beam)",
        "membrane": "Membrane (memb)",
    },
    "Heat Transfer": {
        "heat_transfer": "Heat Transfer in Solids (ht)",
        "conjugate_ht": "Conjugate Heat Transfer (cht)",
        "radiation": "Radiation (rad)",
    },
    "Fluid Flow": {
        "laminar_flow": "Laminar Flow (spf)",
        "turbulent_flow": "Turbulent Flow (spf)",
        "creeping_flow": "Creeping Flow (brinkman)",
    },
    "Acoustics": {
        "pressure_acoustics": "Pressure Acoustics (acpr)",
        "thermoacoustics": "Thermoacoustics (ta)",
    },
    "Chemical": {
        "transport_diluted": "Transport of Diluted Species (tds)",
        "reaction_engineering": "Reaction Engineering (re)",
    },
    "Optics": {
        "ray_optics": "Geometrical Optics (gop)",
        "wave_optics": "Wave Optics (ewfd)",
    },
    "Multiphysics": {
        "thermal_stress": "Thermal Stress (ts)",
        "fluid_structure": "Fluid-Structure Interaction (fsi)",
        "electromechanical": "Electromechanical Forces",
        "joule_heating": "Joule Heating (jh)",
    },
}


def register_physics_tools(mcp: FastMCP) -> None:
    """Register physics tools with the MCP server."""
    
    @mcp.tool()
    def physics_list(model_name: Optional[str] = None) -> dict:
        """
        List all physics interfaces defined in a model.
        
        Args:
            model_name: Model name (default: current model)
        
        Returns:
            List of physics interface names
        """
        model = session_manager.get_model(model_name)
        if model is None:
            return {
                "success": False,
                "error": f"Model not found: {model_name or 'no current model'}"
            }
        
        try:
            physics = model.physics()
            multiphysics = model.multiphysics()
            
            return {
                "success": True,
                "physics": physics,
                "multiphysics": multiphysics,
                "physics_count": len(physics),
                "multiphysics_count": len(multiphysics),
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to list physics: {str(e)}"}
    
    @mcp.tool()
    def physics_get_available() -> dict:
        """
        Get a list of available physics interfaces organized by category.
        
        Returns:
            Dictionary of physics categories and their interfaces
        """
        return {
            "success": True,
            "interfaces": PHYSICS_INTERFACES,
            "note": "Interface identifiers (in parentheses) are used when adding physics.",
        }
    
    @mcp.tool()
    def physics_add(
        physics_type: str,
        component_name: Optional[str] = None,
        model_name: Optional[str] = None
    ) -> dict:
        """
        Add a physics interface to the model.

        Common physics types:
        - "Electrostatics" or "es": Electrostatic field analysis
        - "ElectricCurrents" or "ec": Electric current conduction
        - "SolidMechanics" or "solid": Structural stress analysis
        - "HeatTransfer" or "ht": Heat transfer in solids
        - "LaminarFlow" or "spf": Fluid dynamics

        Args:
            physics_type: Type identifier (e.g., "Electrostatics", "es")
            component_name: Component to add physics to (default: first component)
            model_name: Model name (default: current model)

        Returns:
            Created physics interface info
        """
        model = session_manager.get_model(model_name)
        if model is None:
            return {
                "success": False,
                "error": f"Model not found: {model_name or 'no current model'}"
            }

        try:
            jm = model.java

            tag = physics_type.replace(" ", "_").lower()
            physics_java = create_physics_interface(
                jm,
                tag,
                physics_type,
                first_geometry_tag(jm),
                component_name or "comp1",
            )

            return {
                "success": True,
                "physics": {
                    "name": physics_java.label() if hasattr(physics_java, 'label') else physics_type,
                    "type": physics_type,
                    "tag": tag,
                    "component": component_name or "comp1",
                }
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to add physics: {str(e)}"}
    
    @mcp.tool()
    def physics_add_electrostatics(
        domain_selection: Optional[str] = None,
        model_name: Optional[str] = None
    ) -> dict:
        """
        Add Electrostatics physics interface for electric field analysis.

        Args:
            domain_selection: Selection name for domains (default: all domains)
            model_name: Model name (default: current model)

        Returns:
            Created physics info
        """
        model = session_manager.get_model(model_name)
        if model is None:
            return {
                "success": False,
                "error": f"Model not found: {model_name or 'no current model'}"
            }

        try:
            jm = model.java
            physics_java = create_physics_interface(jm, "es", "Electrostatics", first_geometry_tag(jm))

            if domain_selection:
                try:
                    physics_java.selection().set(domain_selection)
                except Exception:
                    pass

            return {
                "success": True,
                "physics": {
                    "name": physics_java.label() if hasattr(physics_java, 'label') else "Electrostatics",
                    "type": "Electrostatics",
                    "tag": "es",
                    "domain_selection": domain_selection,
                }
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to add Electrostatics: {str(e)}"}
    
    @mcp.tool()
    def physics_add_solid_mechanics(
        domain_selection: Optional[str] = None,
        model_name: Optional[str] = None
    ) -> dict:
        """
        Add Solid Mechanics physics for structural analysis.

        Args:
            domain_selection: Selection name for domains (default: all domains)
            model_name: Model name (default: current model)

        Returns:
            Created physics info
        """
        model = session_manager.get_model(model_name)
        if model is None:
            return {
                "success": False,
                "error": f"Model not found: {model_name or 'no current model'}"
            }

        try:
            jm = model.java
            physics_java = create_physics_interface(jm, "solid", "SolidMechanics", first_geometry_tag(jm))

            if domain_selection:
                try:
                    physics_java.selection().set(domain_selection)
                except Exception:
                    pass

            return {
                "success": True,
                "physics": {
                    "name": physics_java.label() if hasattr(physics_java, 'label') else "Solid Mechanics",
                    "type": "SolidMechanics",
                    "tag": "solid",
                    "domain_selection": domain_selection,
                }
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to add Solid Mechanics: {str(e)}"}
    
    @mcp.tool()
    def physics_add_heat_transfer(
        domain_selection: Optional[str] = None,
        model_name: Optional[str] = None
    ) -> dict:
        """
        Add Heat Transfer physics for thermal analysis.

        Args:
            domain_selection: Selection name for domains (default: all domains)
            model_name: Model name (default: current model)

        Returns:
            Created physics info
        """
        model = session_manager.get_model(model_name)
        if model is None:
            return {
                "success": False,
                "error": f"Model not found: {model_name or 'no current model'}"
            }

        try:
            jm = model.java
            physics_java = create_physics_interface(jm, "ht", "HeatTransfer", first_geometry_tag(jm))

            if domain_selection:
                try:
                    physics_java.selection().set(domain_selection)
                except Exception:
                    pass

            return {
                "success": True,
                "physics": {
                    "name": physics_java.label() if hasattr(physics_java, 'label') else "Heat Transfer",
                    "type": "HeatTransfer",
                    "tag": "ht",
                    "domain_selection": domain_selection,
                }
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to add Heat Transfer: {str(e)}"}
    
    @mcp.tool()
    def physics_add_laminar_flow(
        domain_selection: Optional[str] = None,
        model_name: Optional[str] = None
    ) -> dict:
        """
        Add Laminar Flow physics for fluid dynamics.

        Args:
            domain_selection: Selection name for domains (default: all domains)
            model_name: Model name (default: current model)

        Returns:
            Created physics info
        """
        model = session_manager.get_model(model_name)
        if model is None:
            return {
                "success": False,
                "error": f"Model not found: {model_name or 'no current model'}"
            }

        try:
            jm = model.java
            physics_java = create_physics_interface(jm, "spf", "LaminarFlow", first_geometry_tag(jm))

            if domain_selection:
                try:
                    physics_java.selection().set(domain_selection)
                except Exception:
                    pass

            return {
                "success": True,
                "physics": {
                    "name": physics_java.label() if hasattr(physics_java, 'label') else "Laminar Flow",
                    "type": "LaminarFlow",
                    "tag": "spf",
                    "domain_selection": domain_selection,
                }
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to add Laminar Flow: {str(e)}"}
    
    @mcp.tool()
    def physics_configure_boundary(
        physics_name: str,
        boundary_condition: str,
        boundary_selection: Sequence[int],
        properties: Optional[dict] = None,
        model_name: Optional[str] = None
    ) -> dict:
        """
        Configure a boundary condition for a physics interface.

        Common boundary conditions for Heat Transfer:
        - "Temperature": Fixed temperature
        - "HeatFlux": Heat flux boundary
        - "ConvectiveHeatFlux": Convection cooling
        - "ThermalInsulation": Thermal insulation (adiabatic)

        Common for Solid Mechanics:
        - "Fixed": Fixed constraint
        - "Roller": Roller constraint
        - "Symmetry": Symmetry plane
        - "BoundaryLoad": Applied force/pressure

        Common for Electrostatics:
        - "Ground": Zero potential boundary
        - "ElectricPotential": Specified voltage
        - "SurfaceChargeDensity": Surface charge
        - "ZeroCharge": Zero normal displacement field

        Args:
            physics_name: Name or label of the physics interface
            boundary_condition: Type of boundary condition (e.g. "Temperature", "HeatFlux")
            boundary_selection: Boundary/edge numbers to apply condition to
            properties: Dictionary of property names and values (e.g. {"T0": "293.15[K]"})
            model_name: Model name (default: current model)

        Returns:
            Created boundary condition info
        """
        model = session_manager.get_model(model_name)
        if model is None:
            return {
                "success": False,
                "error": f"Model not found: {model_name or 'no current model'}"
            }

        properties = properties or {}

        try:
            jm = model.java

            physics_java = _find_physics_java(jm, physics_name)

            if physics_java is None:
                return {"success": False, "error": f"Physics interface not found: {physics_name}"}

            tag = _make_tag(boundary_condition.lower())
            legacy = is_legacy_model(jm)
            geometry = None
            if legacy:
                geometry_tag = first_geometry_tag(jm)
                if not geometry_tag:
                    return {"success": False, "error": "No geometry sequence found for boundary condition."}
                geometry = jm.geom(geometry_tag)
            bc = _create_boundary_feature(physics_java, geometry, tag, boundary_condition, legacy)
            bc.selection().set([int(b) for b in boundary_selection])

            if properties:
                for prop_name, prop_value in properties.items():
                    try:
                        bc.set(prop_name, prop_value)
                    except Exception:
                        pass

            bc.label(f'{boundary_condition} (Boundaries {list(boundary_selection)})')

            return {
                "success": True,
                "boundary_condition": {
                    "name": tag,
                    "type": boundary_condition,
                    "physics": physics_name,
                    "selection": list(boundary_selection),
                    "properties": properties,
                }
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to configure boundary: {str(e)}"}
    
    @mcp.tool()
    def physics_set_material(
        physics_name: str,
        material_name: str,
        domain_selection: Optional[Sequence[int]] = None,
        properties: Optional[dict[str, str]] = None,
        model_name: Optional[str] = None
    ) -> dict:
        """
        Assign a material to physics domains.

        This tool tries to add the material from COMSOL's built-in library
        if it's not already in the model.

        Args:
            physics_name: Name of the physics interface
            material_name: Name of the material (e.g. "Silicon", "Steel AISI 4340", "Copper")
            domain_selection: Domain numbers (default: all domains for this physics)
            properties: Optional COMSOL material properties. For example,
                {"thermalconductivity": "1[W/(m*K)]"}. Common heat-transfer
                materials use built-in default values when this argument is omitted.
            model_name: Model name (default: current model)

        Returns:
            Assignment confirmation
        """
        model = session_manager.get_model(model_name)
        if model is None:
            return {
                "success": False,
                "error": f"Model not found: {model_name or 'no current model'}"
            }

        try:
            jm = model.java
            materials = model.materials()
            tag = material_name.replace(" ", "_").replace("-", "_")
            comp = component_containers(jm)[0]

            if material_name not in materials:
                try:
                    mat = comp.material().create(tag, "Common")
                    mat.label(material_name)
                except Exception as e:
                    return {"success": False, "error": f"Could not create material node: {str(e)}"}

            physics_java = _find_physics_java(jm, physics_name)

            if physics_java is None:
                return {"success": False, "error": f"Physics interface not found: {physics_name}"}

            mat_node = comp.material(tag)
            if domain_selection:
                mat_node.selection().set([int(d) for d in domain_selection])

            material_properties = properties or THERMAL_MATERIAL_PROPERTIES.get(material_name.casefold())
            applied_properties = {}
            if material_properties:
                applied_properties = _set_material_properties(mat_node, material_properties)

            return {
                "success": True,
                "material": material_name,
                "physics": physics_name,
                "domain_selection": list(domain_selection) if domain_selection else "all",
                "properties": applied_properties,
                "message": f"Material '{material_name}' assigned to physics '{physics_name}'",
                "warning": None if applied_properties else "No properties were supplied for this material. Set properties before solving.",
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to set material: {str(e)}"}
    
    @mcp.tool()
    def multiphysics_add(
        coupling_type: str,
        physics_list: Sequence[str],
        model_name: Optional[str] = None
    ) -> dict:
        """
        Add a multiphysics coupling between physics interfaces.
        
        Common coupling types:
        - "ThermalStress": Couples Heat Transfer and Solid Mechanics
        - "FluidStructureInteraction": Couples Fluid Flow and Solid Mechanics
        - "ElectromechanicalForces": Couples Electrostatics and Solid Mechanics
        - "JouleHeating": Couples Electric Currents and Heat Transfer
        
        Args:
            coupling_type: Type of multiphysics coupling
            physics_list: Names of physics interfaces to couple
            model_name: Model name (default: current model)
        
        Returns:
            Created coupling info
        """
        model = session_manager.get_model(model_name)
        if model is None:
            return {
                "success": False,
                "error": f"Model not found: {model_name or 'no current model'}"
            }
        
        try:
            if is_legacy_model(model.java):
                geometry_tag = first_geometry_tag(model.java)
                if not geometry_tag:
                    return {"success": False, "error": "Create a geometry before adding a multiphysics coupling."}
                coupling_name, geometry_tag, dimension = _resolve_legacy_multiphysics(
                    coupling_type,
                    geometry_tag,
                    model.java.geom(geometry_tag),
                )
                coupling_node = model.java.multiphysics().create(
                    _make_tag("cpl"), coupling_name, geometry_tag, dimension
                )
            else:
                coupling_node = model.create("multiphysics", coupling_type)
            
            return {
                "success": True,
                "coupling": {
                    "name": coupling_node.name() if hasattr(coupling_node, 'name') else coupling_type,
                    "type": coupling_type,
                    "physics": list(physics_list),
                }
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to add multiphysics: {str(e)}"}
    
    @mcp.tool()
    def physics_list_features(
        physics_name: str,
        model_name: Optional[str] = None
    ) -> dict:
        """
        List all features (boundary conditions, domain settings) in a physics interface.
        
        Args:
            physics_name: Name of the physics interface
            model_name: Model name (default: current model)
        
        Returns:
            List of physics features
        """
        model = session_manager.get_model(model_name)
        if model is None:
            return {
                "success": False,
                "error": f"Model not found: {model_name or 'no current model'}"
            }
        
        try:
            physics_java = _find_physics_java(model.java, physics_name)
            if physics_java is None:
                return {"success": False, "error": f"Physics interface not found: {physics_name}"}

            if is_legacy_model(model.java):
                features = _physics_feature_info(physics_java.feature())
            else:
                physics_node = model / "physics" / physics_name
                features = []
                for child in physics_node.children():
                    feat_info = {"name": child.name()}
                    try:
                        feat_info["type"] = child.type() if hasattr(child, 'type') else "unknown"
                    except Exception:
                        pass
                    features.append(feat_info)
            
            return {
                "success": True,
                "physics": physics_name,
                "features": features,
                "count": len(features),
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to list features: {str(e)}"}
    
    @mcp.tool()
    def physics_remove(
        physics_name: str,
        model_name: Optional[str] = None
    ) -> dict:
        """
        Remove a physics interface from the model.
        
        Args:
            physics_name: Name of the physics interface to remove
            model_name: Model name (default: current model)
        
        Returns:
            Removal confirmation
        """
        model = session_manager.get_model(model_name)
        if model is None:
            return {
                "success": False,
                "error": f"Model not found: {model_name or 'no current model'}"
            }
        
        try:
            if is_legacy_model(model.java):
                physics_java = _find_physics_java(model.java, physics_name)
                if physics_java is None:
                    return {"success": False, "error": f"Physics interface not found: {physics_name}"}
                model.java.physics().remove(physics_java.tag())
            else:
                physics_interfaces = model.physics()
                if physics_name not in physics_interfaces:
                    return {"success": False, "error": f"Physics interface not found: {physics_name}"}
                physics_node = model / "physics" / physics_name
                model.remove(physics_node)
            
            return {
                "success": True,
                "removed": physics_name,
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to remove physics: {str(e)}"}
    
    @mcp.tool()
    def geometry_get_boundaries(
        geometry_name: Optional[str] = None,
        component_name: str = "comp1",
        model_name: Optional[str] = None
    ) -> dict:
        """
        Get all boundaries from a geometry with their properties.

        Use this to identify which boundary numbers correspond to which faces
        before setting boundary conditions.

        Args:
            geometry_name: Geometry sequence name (default: first geometry)
            component_name: Component name (default: 'comp1')
            model_name: Model name (default: current model)

        Returns:
            List of boundaries with their numbers and areas
        """
        model = session_manager.get_model(model_name)
        if model is None:
            return {
                "success": False,
                "error": f"Model not found: {model_name or 'no current model'}"
            }

        try:
            jm = model.java

            comp = component_container(jm, component_name)
            if comp is None:
                return {"success": False, "error": f"Component '{component_name}' not found."}

            geom_tag = geometry_name
            if not geom_tag:
                geom_tag = first_geometry_tag(jm)
                if not geom_tag:
                    return {"success": False, "error": "No geometries in component."}

            geom = comp.geom(geom_tag)
            geom.run()

            nboundary, ndomain = geometry_entity_counts(geom)

            boundaries = []
            for i in range(1, nboundary + 1):
                try:
                    bd_info = {"boundary_number": i}
                    boundaries.append(bd_info)
                except Exception:
                    boundaries.append({"boundary_number": i, "error": "Could not get info"})

            return {
                "success": True,
                "geometry": geom_tag,
                "total_boundaries": nboundary,
                "total_domains": ndomain,
                "boundaries": boundaries,
                "hint": "Use boundary_number to set boundary conditions with physics_configure_boundary",
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to get boundaries: {str(e)}"}
    
    @mcp.tool()
    def physics_interactive_setup_flow(
        physics_name: str = "Laminar Flow",
        model_name: Optional[str] = None
    ) -> dict:
        """
        Interactive setup wizard for Laminar Flow boundary conditions.
        
        This tool helps identify and configure flow boundary conditions:
        1. Lists all available boundaries
        2. Prompts user to select inlet, outlet, and wall boundaries
        3. Configures appropriate boundary conditions
        
        Args:
            physics_name: Name of the Laminar Flow physics interface
            model_name: Model name (default: current model)
        
        Returns:
            Boundary information and setup instructions
        """
        model = session_manager.get_model(model_name)
        if model is None:
            return {
                "success": False,
                "error": f"Model not found: {model_name or 'no current model'}"
            }
        
        try:
            # Get geometry boundaries
            boundaries_info = geometry_get_boundaries(model_name=model_name)
            if not boundaries_info.get("success"):
                return boundaries_info
            
            return {
                "success": True,
                "message": "Interactive Flow Setup - Please specify boundaries",
                "available_boundaries": boundaries_info["total_boundaries"],
                "boundaries": boundaries_info["boundaries"],
                "setup_instructions": {
                    "step1": "Identify which boundary numbers are INLETS (flow enters)",
                    "step2": "Identify which boundary numbers are OUTLETS (flow exits)",
                    "step3": "Use physics_configure_boundary to set conditions",
                },
                "boundary_condition_types": {
                    "InletBoundary": "Set inlet velocity (U0 parameter)",
                    "OutletBoundary": "Set outlet pressure (p0 parameter, default 0)",
                    "Wall": "No-slip wall (default for unspecified boundaries)",
                    "Symmetry": "Symmetry plane",
                },
                "example_usage": {
                    "inlet": "physics_configure_boundary(physics_name='Laminar Flow', boundary_condition='InletBoundary', boundary_selection=[1, 2], properties={'U0': '1[mm/s]'})",
                    "outlet": "physics_configure_boundary(physics_name='Laminar Flow', boundary_condition='OutletBoundary', boundary_selection=[3])",
                },
                "next_step": "Please tell me which boundary numbers to use for inlet(s) and outlet(s)",
            }
        except Exception as e:
            return {"success": False, "error": f"Interactive setup failed: {str(e)}"}
    
    @mcp.tool()
    def physics_setup_flow_boundaries(
        physics_name: str,
        inlet_boundaries: Sequence[int],
        outlet_boundaries: Sequence[int],
        inlet_velocity: str = "1[mm/s]",
        outlet_pressure: str = "0",
        model_name: Optional[str] = None
    ) -> dict:
        """
        Setup Laminar Flow boundary conditions with specified boundaries.
        
        This tool configures inlet velocity and outlet pressure boundary conditions
        for a fluid flow simulation.
        
        Args:
            physics_name: Name of the Laminar Flow physics interface
            inlet_boundaries: List of boundary numbers for inlets
            outlet_boundaries: List of boundary numbers for outlets
            inlet_velocity: Inlet velocity expression (default: "1[mm/s]")
            outlet_pressure: Outlet pressure expression (default: "0")
            model_name: Model name (default: current model)
        
        Returns:
            Configuration confirmation
        """
        model = session_manager.get_model(model_name)
        if model is None:
            return {
                "success": False,
                "error": f"Model not found: {model_name or 'no current model'}"
            }
        
        try:
            jm = model.java
            
            physics_java = _find_physics_java(jm, physics_name)

            if physics_java is None:
                return {"success": False, "error": f"Could not find physics interface: {physics_name}"}

            legacy = is_legacy_model(jm)
            geometry = jm.geom(first_geometry_tag(jm)) if legacy else None

            results = {"inlets": [], "outlets": []}

            for i, boundary in enumerate(inlet_boundaries):
                inlet_tag = _make_tag("inl")
                inlet = _create_boundary_feature(physics_java, geometry, inlet_tag, "Inlet", legacy)
                inlet.selection().set([int(boundary)])
                inlet.set(_boundary_property_name("Inlet", "U0", legacy), inlet_velocity)
                inlet.label(f'Inlet {i+1} (Boundary {boundary})')
                results["inlets"].append({
                    "tag": inlet_tag,
                    "boundary": boundary,
                    "velocity": inlet_velocity
                })
            
            for i, boundary in enumerate(outlet_boundaries):
                outlet_tag = _make_tag("out")
                outlet = _create_boundary_feature(physics_java, geometry, outlet_tag, "Outlet", legacy)
                outlet.selection().set([int(boundary)])
                outlet.set('p0', outlet_pressure)
                outlet.label(f'Outlet {i+1} (Boundary {boundary})')
                results["outlets"].append({
                    "tag": outlet_tag,
                    "boundary": boundary,
                    "pressure": outlet_pressure
                })
            
            return {
                "success": True,
                "physics": physics_name,
                "configured_boundaries": results,
                "inlet_velocity": inlet_velocity,
                "outlet_pressure": outlet_pressure,
                "message": f"Configured {len(inlet_boundaries)} inlet(s) and {len(outlet_boundaries)} outlet(s)",
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to setup boundaries: {str(e)}"}

    @mcp.tool()
    def physics_interactive_setup_heat(
        physics_name: str = "Heat Transfer in Solids",
        model_name: Optional[str] = None
    ) -> dict:
        """
        Interactive setup wizard for Heat Transfer boundary conditions.
        
        This tool helps identify and configure thermal boundary conditions:
        1. Lists all available boundaries
        2. Shows typical boundary condition types for thermal analysis
        3. Provides setup instructions
        
        Args:
            physics_name: Name of the Heat Transfer physics interface
            model_name: Model name (default: current model)
        
        Returns:
            Boundary information and setup instructions
        """
        model = session_manager.get_model(model_name)
        if model is None:
            return {
                "success": False,
                "error": f"Model not found: {model_name or 'no current model'}"
            }
        
        try:
            boundaries_info = geometry_get_boundaries(model_name=model_name)
            if not boundaries_info.get("success"):
                return boundaries_info
            
            return {
                "success": True,
                "message": "Interactive Heat Transfer Setup",
                "available_boundaries": boundaries_info["total_boundaries"],
                "boundaries": boundaries_info["boundaries"],
                "boundary_condition_types": {
                    "TemperatureBoundary": "Fixed temperature (heat sink/source)",
                    "HeatFluxBoundary": "Prescribed heat flux (heat source)",
                    "ConvectiveHeatFlux": "Convection cooling/heating",
                    "Symmetry": "Symmetry plane (adiabatic)",
                    "ThermalInsulation": "Thermal insulation (default)"
                },
                "typical_setup": {
                    "heat_source": "Use HeatFluxBoundary with q0 parameter (W/m^2)",
                    "heat_sink": "Use TemperatureBoundary with T0 parameter (K or degC)",
                    "convection": "Use ConvectiveHeatFlux with h and Text parameters"
                },
                "example_usage": {
                    "heat_source": "physics_setup_heat_boundaries(physics_name='Heat Transfer in Solids', heat_flux_boundaries=[1, 2], heat_flux_value='1e6[W/m^2]')",
                    "heat_sink": "physics_setup_heat_boundaries(physics_name='Heat Transfer in Solids', temperature_boundaries=[3], temperature_value='293.15[K]')"
                },
                "next_step": "Tell me which boundary numbers to use for heat source and heat sink",
            }
        except Exception as e:
            return {"success": False, "error": f"Interactive setup failed: {str(e)}"}

    @mcp.tool()
    def physics_setup_heat_boundaries(
        physics_name: str,
        heat_flux_boundaries: Optional[Sequence[int]] = None,
        temperature_boundaries: Optional[Sequence[int]] = None,
        convection_boundaries: Optional[Sequence[int]] = None,
        heat_flux_value: str = "1e6[W/m^2]",
        temperature_value: str = "293.15[K]",
        convection_coeff: str = "10[W/(m^2*K)]",
        ambient_temp: str = "293.15[K]",
        model_name: Optional[str] = None
    ) -> dict:
        """
        Setup Heat Transfer boundary conditions with specified boundaries.
        
        This tool configures thermal boundary conditions for heat transfer simulation:
        - Heat flux boundaries (heat sources)
        - Temperature boundaries (heat sinks)
        - Convective cooling/heating boundaries
        
        Args:
            physics_name: Name of the Heat Transfer physics interface
            heat_flux_boundaries: List of boundary numbers for heat flux
            temperature_boundaries: List of boundary numbers for fixed temperature
            convection_boundaries: List of boundary numbers for convection
            heat_flux_value: Heat flux value (default: "1e6[W/m^2]")
            temperature_value: Temperature value (default: "293.15[K]" = 20°C)
            convection_coeff: Convection coefficient (default: "10[W/(m^2*K)]")
            ambient_temp: Ambient temperature for convection (default: "293.15[K]")
            model_name: Model name (default: current model)
        
        Returns:
            Configuration confirmation
        """
        model = session_manager.get_model(model_name)
        if model is None:
            return {
                "success": False,
                "error": f"Model not found: {model_name or 'no current model'}"
            }

        heat_flux_boundaries = heat_flux_boundaries or []
        temperature_boundaries = temperature_boundaries or []
        convection_boundaries = convection_boundaries or []

        try:
            jm = model.java

            physics_java = _find_physics_java(jm, physics_name)

            if physics_java is None:
                return {"success": False, "error": f"Could not find physics interface: {physics_name}"}

            legacy = is_legacy_model(jm)
            geometry = jm.geom(first_geometry_tag(jm)) if legacy else None

            results = {"heat_flux": [], "temperature": [], "convection": []}

            for i, boundary in enumerate(heat_flux_boundaries):
                tag = _make_tag("hf")
                bc = _create_boundary_feature(physics_java, geometry, tag, "HeatFlux", legacy)
                bc.selection().set([int(boundary)])
                bc.set('q0', heat_flux_value)
                bc.label(f'Heat Flux {i+1} (Boundary {boundary})')
                results["heat_flux"].append({
                    "tag": tag,
                    "boundary": boundary,
                    "heat_flux": heat_flux_value
                })
            
            for i, boundary in enumerate(temperature_boundaries):
                tag = _make_tag("temp")
                bc = _create_boundary_feature(physics_java, geometry, tag, "Temperature", legacy)
                bc.selection().set([int(boundary)])
                bc.set('T0', temperature_value)
                bc.label(f'Temperature {i+1} (Boundary {boundary})')
                results["temperature"].append({
                    "tag": tag,
                    "boundary": boundary,
                    "temperature": temperature_value
                })
            
            for i, boundary in enumerate(convection_boundaries):
                tag = _make_tag("conv")
                bc = _create_boundary_feature(physics_java, geometry, tag, "ConvectiveHeatFlux", legacy)
                bc.selection().set([int(boundary)])
                bc.set('h', convection_coeff)
                bc.set('Text', ambient_temp)
                bc.label(f'Convection {i+1} (Boundary {boundary})')
                results["convection"].append({
                    "tag": tag,
                    "boundary": boundary,
                    "h": convection_coeff,
                    "T_amb": ambient_temp
                })
            
            return {
                "success": True,
                "physics": physics_name,
                "configured_boundaries": results,
                "summary": {
                    "heat_flux_boundaries": len(heat_flux_boundaries),
                    "temperature_boundaries": len(temperature_boundaries),
                    "convection_boundaries": len(convection_boundaries)
                },
                "message": f"Configured {len(heat_flux_boundaries)} heat flux, {len(temperature_boundaries)} temperature, and {len(convection_boundaries)} convection boundaries",
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to setup heat boundaries: {str(e)}"}

    @mcp.tool()
    def physics_boundary_selection(
        physics_name: str,
        boundary_condition_type: str,
        boundary_numbers: Sequence[int],
        properties: Optional[dict] = None,
        model_name: Optional[str] = None
    ) -> dict:
        """
        Generic boundary condition setup with boundary selection.

        Use this tool to configure any boundary condition by specifying:
        1. The physics interface name
        2. The boundary condition type
        3. The boundary numbers to apply the condition to
        4. Properties specific to the boundary condition

        Common boundary condition types by physics:

        Heat Transfer (ht):
        - Temperature: Set T0 (temperature)
        - HeatFlux: Set q0 (heat flux)
        - ConvectiveHeatFlux: Set h (coefficient), Text (ambient temp)

        Laminar Flow (spf):
        - InletBoundary: Set U0 (velocity)
        - OutletBoundary: Set p0 (pressure)
        - Wall: No-slip wall

        Solid Mechanics (solid):
        - Fixed: Fixed constraint
        - BoundaryLoad: Set Fx, Fy, Fz or FAx, FAy, FAz

        Args:
            physics_name: Name or label of the physics interface
            boundary_condition_type: Type of boundary condition
            boundary_numbers: List of boundary numbers
            properties: Dictionary of property names and values
            model_name: Model name (default: current model)

        Returns:
            Configuration confirmation
        """
        model = session_manager.get_model(model_name)
        if model is None:
            return {
                "success": False,
                "error": f"Model not found: {model_name or 'no current model'}"
            }

        properties = properties or {}

        try:
            jm = model.java

            physics_java = _find_physics_java(jm, physics_name)

            if physics_java is None:
                return {"success": False, "error": f"Physics interface not found: {physics_name}"}

            tag = _make_tag("bc")
            bc = physics_java.create(tag, boundary_condition_type)
            bc.selection().set([int(b) for b in boundary_numbers])

            for prop_name, prop_value in properties.items():
                try:
                    bc.set(prop_name, prop_value)
                except Exception:
                    pass

            bc.label(f'{boundary_condition_type} (Boundaries {list(boundary_numbers)})')

            return {
                "success": True,
                "physics": physics_name,
                "boundary_condition": {
                    "type": boundary_condition_type,
                    "tag": tag,
                    "boundaries": list(boundary_numbers),
                    "properties": properties
                },
                "message": f"Created {boundary_condition_type} on boundaries {list(boundary_numbers)}",
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to create boundary condition: {str(e)}"}


