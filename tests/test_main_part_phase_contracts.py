from shader_toolchain.main_part_phase_contracts import (
    contract_is_typed,
    fixture_closure,
    phase_contract_registry,
    resource_closure,
)


def test_phase_contracts_make_dataflow_resources_and_fixtures_explicit() -> None:
    contracts = phase_contract_registry()
    material = contracts["material.glass"]
    assert material.inputs[0].name == "viewPosition"
    assert material.outputs[0].type_name == "MainPartDissolveGlassMaterial"
    assert material.port_source == "curated"
    assert contract_is_typed(material)
    reflection = contracts["reflection.multi"]
    assert any(resource.name == "CB_REFLECTIONS"
               for resource in reflection.resources)
    assert "cluster_reflection_masks" in reflection.activation_fixtures


def test_contract_closures_deduplicate_runtime_requirements() -> None:
    phases = ("material.glass", "lighting.standard", "reflection.multi")
    resources = resource_closure(phases)
    assert len(resources) == len({
        (resource.kind, resource.slot, resource.name) for resource in resources
    })
    fixtures = fixture_closure(phases)
    assert fixtures == tuple(sorted(set(fixtures)))
    assert "directional_light" in fixtures


def test_existing_helper_signatures_generate_contract_ports() -> None:
    contracts = phase_contract_registry()
    normal = contracts["normal.tangent_map"]
    assert normal.symbol == "DecodeMainPartTwoSidedNormal"
    assert normal.port_source == "inferred"
    assert normal.inputs
    assert normal.outputs[0].type_name == "float3"
    assert contract_is_typed(contracts["coverage.opaque"])
