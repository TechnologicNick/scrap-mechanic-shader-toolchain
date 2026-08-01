from shader_toolchain.main_part_phase_compiler import (
    compile_main_part_phase_graph,
)
from shader_toolchain.recipes.main_part_glass_surface_families import (
    MEDIUM_MULTI_STANDARD,
)
from shader_toolchain.recipes.main_part_graph_templates import (
    MAIN_PART_GRAPH_TEMPLATES,
)


SOURCE = '''
cbuffer CB_PERFRAME : register(b12) { float4 perFrame; }
cbuffer CB_PROJECTION : register(b5) { float4 projection; }
cbuffer CB_REFLECTIONS : register(b11) { float4 reflections; }
cbuffer CB_GLASS { float4 glass; }
cbuffer Cluster : register(b6) { float4 cluster; }
cbuffer LightProps : register(b8) { float4 lights; }
Texture2D<float4> tDif : register(t0);
// 3Dmigoto declarations
#define cmp -
void commonPS(
  float4 v0 : SV_Position0, float3 v1 : VIEW_POSITION0,
  float2 v2 : UV0, float3 v3 : NORMAL0, float3 v4 : TANGENT0,
  float3 v5 : BITANGENT0, float4 v6 : VERTEXCOLOR0,
  linear noperspective centroid float3 v7 : SCREEN_UV0,
  float4 v8 : FOG_COLOR0, uint v9 : SV_IsFrontFace0,
  out float4 o0 : SV_Target0, out float4 o1 : SV_Target1) {}
'''


def test_compiler_routes_a_complete_descriptor_through_a_graph_template() -> None:
    compiled = compile_main_part_phase_graph(
        MEDIUM_MULTI_STANDARD.defines, SOURCE, selector="SM_SHADER_TEST"
    )
    assert compiled is not None
    assert compiled.template == "transparent_glass_surface"
    assert compiled.family.endswith("unresponsive_standard")
    assert compiled.descriptor.selector == "SM_SHADER_TEST"
    assert "EvaluateMainPartGlassSurfaceMedium" in compiled.source
    assert "partPositionState" not in compiled.source


def test_compiler_refuses_phase_complete_but_unvalidated_wiring() -> None:
    defines = {
        "PIXEL_SHADER", "PS_PERM_TRANSPARANT_BEHIND", "PS_GLASS",
        "PS_ASG_TEX", "PS_REFLECTION_MULTI",
    }
    assert compile_main_part_phase_graph(defines, SOURCE) is None


def test_graph_templates_are_declarative_and_uniquely_named() -> None:
    names = [template.name for template in MAIN_PART_GRAPH_TEMPLATES]
    assert names == [
        "tinted_dissolve_glass_surface",
        "transparent_glass_surface",
        "directional_glass_surface",
    ]
    assert len(names) == len(set(names))
