from pathlib import Path

from shader_toolchain.main_part_phase_compiler import (
    compile_main_part_phase_graph,
)
from shader_toolchain.recipes.main_part_directional_glass_surface import (
    DIRECTIONAL_GLASS_SURFACES,
    classify_main_part_directional_glass_surface,
    lift_main_part_directional_glass_surface,
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
  float2 v2 : UV0, float3 v3 : NORMAL0, float4 v4 : VERTEXCOLOR0,
  linear noperspective centroid float3 v5 : SCREEN_UV0,
  float4 v6 : FOG_COLOR0, uint v7 : SV_IsFrontFace0,
  out float4 o0 : SV_Target0, out float4 o1 : SV_Target1) {}
'''


def test_directional_glass_template_classifies_quality_reflection_axes() -> None:
    assert len(DIRECTIONAL_GLASS_SURFACES) == 9
    for policy in DIRECTIONAL_GLASS_SURFACES:
        assert classify_main_part_directional_glass_surface(
            policy.defines, SOURCE
        ) == policy
        assert classify_main_part_directional_glass_surface(
            policy.defines | {"PS_TRANSMISSION"}, SOURCE
        ) is None


def test_directional_glass_wrapper_is_typed_and_selector_independent() -> None:
    policy = DIRECTIONAL_GLASS_SURFACES[-1]
    result = lift_main_part_directional_glass_surface(policy.defines, SOURCE)
    assert result is not None
    family, lifted = result
    assert family == policy.name
    assert "EvaluateMainPartDirectionalGlassSurface" in lifted
    assert "main_part_directional_glass_surface.hlsl" in lifted
    assert "partPositionState" not in lifted
    assert "SM_SHADER_" not in lifted


def test_phase_compiler_routes_directional_glass_graph() -> None:
    policy = DIRECTIONAL_GLASS_SURFACES[0]
    compiled = compile_main_part_phase_graph(
        policy.defines, SOURCE, selector="SM_SHADER_TEST"
    )
    assert compiled is not None
    assert compiled.template == "directional_glass_surface"
    assert compiled.family == policy.name


def test_directional_glass_asset_exposes_semantic_phase_boundaries() -> None:
    asset = Path(
        "src/shader_toolchain/recipes/assets/"
        "main_part_directional_glass_surface.hlsl"
    ).read_text(encoding="utf-8")
    for helper in (
        "EvaluateMainPartDirectionalGlassMaterial",
        "EvaluateMainPartDirectionalMapGlassLighting",
        "EvaluateMainPartHighDirectionalGlassLighting",
        "EvaluateMainPartGlassLocalLights",
        "EvaluateMainPartGlassReflectionProbes",
        "EvaluateMainPartSingleReflection",
        "ComposeMainPartUnresponsiveGlassSurface",
        "ComposeMainPartHighUnresponsiveGlassSurface",
        "EvaluateMainPartDirectionalGlassSurface",
    ):
        assert helper in asset
    assert "partPositionState" not in asset
    assert "../phases/" not in asset


def test_high_quality_backend_is_split_from_material_and_cluster_traversal() -> None:
    asset = Path(
        "src/shader_toolchain/recipes/assets/"
        "main_part_glass_high_quality.hlsl"
    ).read_text(encoding="utf-8")
    for helper in (
        "ResolveMainPartCascade",
        "SampleMainPartCascadeTent",
        "EvaluateMainPartCascadeVisibility",
        "EvaluateMainPartCloudOcclusion",
        "EvaluateMainPartHighDirectionalGlassLighting",
        "ComposeMainPartHighUnresponsiveGlassSurface",
    ):
        assert helper in asset
    assert "EvaluateMainPartGlassLocalLights" not in asset
    assert "EvaluateMainPartGlassReflectionProbes" not in asset
    assert "partPositionState" not in asset
