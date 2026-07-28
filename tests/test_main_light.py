from pathlib import Path

from shader_toolchain.recipes.main_light import (
    _execution,
    _emit_variant_snippets,
    _is_clustered_local_compact,
    _lift_clustered_local_compact,
    _lift_main_light_abi,
)


def test_main_light_abi_lift_names_each_recovered_buffer() -> None:
    source = """cbuffer CB_PROJECTION : register(b5) { float4 projection; }
cbuffer CB_PERFRAME : register(b12) { float4 perFrame; }
cbuffer Cluster : register(b0) { float4 cluster; }
cbuffer LightProps : register(b1) { float4 light; }
void mainPS() {}
"""

    lifted = _lift_main_light_abi(source)

    assert '#include "include/main_light_projection_abi.hlsl"' in lifted
    assert '#include "include/main_light_perframe_abi.hlsl"' in lifted
    assert '#include "include/main_light_cluster_abi.hlsl"' in lifted
    assert '#include "include/main_light_lightprops_abi.hlsl"' in lifted
    assert "cbuffer " not in lifted


def test_clustered_local_low_lift_is_a_semantic_entry_point() -> None:
    source = """Texture2D<float4> tDif : register(t0);
// 3Dmigoto declarations
#define cmp -
void mainPS(float4 v0, float2 v1, out float3 o0) { o0 = 0; }
"""

    lifted = _lift_clustered_local_compact(source)

    assert '#include "../main_light_clustered_local.hlsl"' in lifted
    assert "EvaluateMainLightClusteredLocal(v1)" in lifted
    assert "3Dmigoto" not in lifted


def test_clustered_local_ortho_lift_selects_orthographic_reconstruction() -> None:
    source = """Texture2D<float4> tDif : register(t0);
// 3Dmigoto declarations
#define cmp -
void mainPS(float4 v0, float2 v1, out float3 o0) { o0 = 0; }
"""

    lifted = _lift_clustered_local_compact(
        source, high_quality=True, orthographic=True
    )

    assert "#define MAIN_LIGHT_COMPACT_HIGH 1" in lifted
    assert "#define MAIN_LIGHT_COMPACT_ORTHO 1" in lifted


def test_clustered_local_lift_covers_low_and_medium_feature_policies() -> None:
    features = [
        "PS_CAMERA_LIGHT",
        "PS_DIRECTIONAL_LIGHT",
        "PS_FLOW_COOKIE",
        "PS_HORIZON_LIGHT",
        "PS_SSS",
        "PS_TEMPORAL_AO_CASCADE",
    ]
    assert _is_clustered_local_compact([
        "PIXEL_SHADER",
        "PS_SHADER_QUALITY_LOW",
        *features,
    ])
    assert _is_clustered_local_compact([
        "PIXEL_SHADER",
        "PS_SHADER_QUALITY_MEDIUM",
        "PS_SHADOW_QUALITY_OFF",
    ])
    assert _is_clustered_local_compact([
        "PIXEL_SHADER",
        "PS_SHADER_QUALITY_HIGH",
    ])
    assert _is_clustered_local_compact([
        "PIXEL_SHADER",
        "PS_SHADER_QUALITY_HIGH",
        "ORTHO",
    ])


def test_main_light_fuzz_fixture_activates_clustered_lights(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "shader_toolchain.recipes.main_light.ShaderReflector.abi",
        lambda self, blob: {
            "resources": [
                {"type": 5, "bind_point": 13, "dimension": 1},
            ],
            "constant_buffers": [
                {"bind_point": slot} for slot in (0, 1, 5, 12)
            ],
        },
    )

    execution = _execution(b"fixture")

    assert execution["structured_inputs"][0]["profile"] == "main-light"
    assert {
        binding["slot"]: binding["profile"]
        for binding in execution["constant_buffers"]
    } == {
        0: "main-light-cluster",
        1: "main-light-lights",
        5: "projection",
        12: "index",
    }


def test_main_light_variants_are_emitted_as_independent_snippets(
    tmp_path: Path,
) -> None:
    bodies = _emit_variant_snippets(
        tmp_path,
        {
            "SM_SHADER_A": """cbuffer Test : register(b0) { float4 value; }
Texture2D<float4> textureA : register(t0);
// 3Dmigoto declarations
#define cmp -


void mainPS(
  float4 v0 : SV_Position0,
  float2 v1 : UNSCALED_UV0,
  out float3 o0 : SV_Target0)
{
  o0 = value.xyz;
}
""",
            "SM_SHADER_B": """cbuffer Test : register(b0) { float4 value; }
Texture2D<float4> textureB : register(t1);
// 3Dmigoto declarations
#define cmp -


void mainPS(
  float4 v0 : SV_Position0,
  float2 v1 : UNSCALED_UV0,
  out float3 o0 : SV_Target0)
{
  o0 = value.zyx;
}
""",
        },
    )

    root = tmp_path / "semantic" / "include" / "main_light"
    assert (root / "SM_SHADER_A.hlsl").is_file()
    assert (root / "SM_SHADER_B.hlsl").is_file()
    assert "Semantic phase map" in (
        root / "SM_SHADER_A.hlsl"
    ).read_text(encoding="utf-8")
    assert "o0 = value.xyz" in (
        root / "SM_SHADER_A.hlsl"
    ).read_text(encoding="utf-8")
    assert "o0 = value.zyx" in (
        root / "SM_SHADER_B.hlsl"
    ).read_text(encoding="utf-8")
    assert bodies == {
        "SM_SHADER_A": '#include "include/main_light/SM_SHADER_A.hlsl"\n',
        "SM_SHADER_B": '#include "include/main_light/SM_SHADER_B.hlsl"\n',
    }
