import json

from shader_toolchain.main_part_synthesis import (
    _suggested_family_name,
    build_operation_ir,
    induce_family_template,
    write_synthesis_specifications,
)


def _source(reflection: str) -> str:
    return f'''Texture2D<float4> tDif : register(t0);
Texture2DArray<float4> taReflection : register(t14);
// 3Dmigoto declarations
void commonPS(
  float3 v1 : VIEW_POSITION0, float2 v2 : UV0,
  out float4 o0 : SV_Target0)
{{
  float4 partPositionState;
  partPositionState = tDif.Load(int3(v2, 0));
  {reflection}
  o0 = partPositionState;
}}
'''


def test_operation_ir_tracks_values_resources_and_outputs() -> None:
    operations = build_operation_ir(_source(
        "partPositionState.xyz += taReflection.Load(int4(0, 0, 0, 0)).xyz;"
    ))
    assert any("tDif" in operation.resources for operation in operations)
    assert any(
        "taReflection" in operation.resources for operation in operations
    )
    assert any("render_target" in operation.effects for operation in operations)
    assert any(operation.reads for operation in operations)


def test_family_anti_unification_infers_reflection_policy_hole() -> None:
    selectors = ("SM_SHADER_A", "SM_SHADER_B", "SM_SHADER_C")
    candidate = {
        "family_key": "fixture",
        "selectors": selectors,
        "skeleton": (
            "material.glass", "reflection.single", "composition.standard"
        ),
        "observed_policies": (
            ("default", "multi"), ("default", "off"),
            ("default", "single"),
        ),
        "selector_policies": {
            selectors[0]: ("default", "multi"),
            selectors[1]: ("default", "off"),
            selectors[2]: ("default", "single"),
        },
        "matrix_complete": True,
    }
    sources = {
        selectors[0]: _source(
            "partPositionState.xyz += taReflection.Load("
            "int4(0, 0, 0, 0)).xyz;"
        ),
        selectors[1]: _source(
            "partPositionState.xyz += float3(0.12, 0.12, 0.12);"
        ),
        selectors[2]: _source(
            "partPositionState.xyz += taReflection.Load("
            "int4(1, 0, 0, 0)).xyz;"
        ),
    }
    template = induce_family_template(candidate, sources)
    assert template.common_operation_ratio > 0
    assert template.holes
    assert any(
        "reflection" in hole.controlled_by for hole in template.holes
    )
    assert any(
        "reflection.single" in hole.matched_phases for hole in template.holes
    )
    assert all(
        value.type_name for hole in template.holes
        for value in (*hole.live_inputs, *hole.live_outputs)
    )


def test_register_names_do_not_change_operation_fingerprints() -> None:
    left = _source("partPositionState.x = partPositionState.y + 1;")
    right = left.replace("partPositionState", "materialSampleState")
    assert [value.fingerprint for value in build_operation_ir(left)] == [
        value.fingerprint for value in build_operation_ir(right)
    ]


def test_family_names_are_semantic_and_never_selector_derived() -> None:
    name = _suggested_family_name((
        "output.transparent_surface", "material.water",
        "coverage.dissolve_uv1", "composition.tinted",
    ))
    assert name == "transparent_surface_water_dissolve_uv1_tinted"
    assert "shader" not in name


def test_ready_family_specs_are_semantic_and_renderer_consumable(tmp_path) -> None:
    report = {
        "templates": [{
            "readiness": "auto_composable",
            "suggested_name": "water_dissolve_uv1_tinted",
            "selectors": ["SM_SHADER_A", "SM_SHADER_B"],
            "skeleton": ["material.water", "coverage.dissolve_uv1"],
            "common_operation_ratio": 0.75,
            "holes": [{
                "suggested_symbol": "EvaluateWaterDissolveCoverage0",
                "controlled_by": ["quality"],
                "live_inputs": [{"name": "%in_uv1", "type_name": "float2"}],
                "live_outputs": [{"name": "%temporary0", "type_name": "float4"}],
                "resources": ["tCutoff"], "effects": ["discard"],
                "matched_phases": ["coverage.dissolve"],
                "variant_members": [["variant", ["SM_SHADER_A"]]],
            }],
        }]
    }
    campaign = write_synthesis_specifications(report, tmp_path)
    assert campaign["family_count"] == 1
    specification = json.loads(
        (tmp_path / "water_dissolve_uv1_tinted.json").read_text()
    )
    assert specification["phases"][0]["inputs"][0]["type_name"] == "float2"
    assert not any("SM_SHADER" in name for name in campaign["specifications"])
