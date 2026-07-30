from shader_toolchain.recipes.main_part import (
    GLASS_OPAQUE_FORWARD_MEDIUM_DEFINES,
    is_main_part_glass_opaque_forward_medium,
    lift_main_part_glass_opaque_forward_medium,
)


def test_glass_opaque_forward_medium_policy_is_exact() -> None:
    defines = sorted(GLASS_OPAQUE_FORWARD_MEDIUM_DEFINES)
    assert is_main_part_glass_opaque_forward_medium(defines)
    assert not is_main_part_glass_opaque_forward_medium(
        [define for define in defines if define != "PS_TEMPORAL_AO_CASCADE"]
    )
    assert not is_main_part_glass_opaque_forward_medium(
        defines + ["PS_MAT_CAP_MASKED_GLOW"]
    )


def test_glass_opaque_forward_medium_uses_shared_abis_and_phases() -> None:
    source = '''cbuffer CB_PERFRAME : register(b12) { float4 perFrame; }
cbuffer CB_PROJECTION : register(b5) { float4 projection; }
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
    lifted = lift_main_part_glass_opaque_forward_medium(source)
    for filename in (
        "main_part_projection_abi.hlsl",
        "main_part_perframe_abi.hlsl",
        "main_part_glass_opaque_abi.hlsl",
        "main_part_cluster_abi.hlsl",
        "main_part_lightprops_abi.hlsl",
        "main_part_glass_opaque_medium.hlsl",
    ):
        assert f'#include "include/{filename}"' in lifted
    assert "partPositionState" not in lifted
    assert "EvaluateMainPartOpaqueGlassForwardMedium" in lifted
    function_body = lifted[lifted.index("void commonPS(") :]
    assert '#include "include/main_part_glass_opaque_medium.hlsl"' not in function_body
