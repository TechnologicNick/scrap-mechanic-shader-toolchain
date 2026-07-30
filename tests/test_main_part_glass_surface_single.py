from shader_toolchain.recipes.main_part import (
    GLASS_SURFACE_SINGLE_TINTED_DEFINES,
    is_main_part_glass_surface_single_tinted,
    lift_main_part_glass_surface_single_tinted,
)


def test_glass_surface_single_policy_is_exact() -> None:
    defines = sorted(GLASS_SURFACE_SINGLE_TINTED_DEFINES)
    assert is_main_part_glass_surface_single_tinted(defines)
    assert not is_main_part_glass_surface_single_tinted(
        [define for define in defines if define != "PS_REFLECTION_SINGLE"]
    )
    assert not is_main_part_glass_surface_single_tinted(
        defines + ["PS_LIGHT_CAP"]
    )


def test_glass_surface_single_lift_preserves_abi_and_factors_body() -> None:
    source = '''cbuffer CB_PERFRAME : register(b12) { float4 perFrame; }
cbuffer CB_PROJECTION : register(b5) { float4 projection; }
cbuffer CB_GLASS { float4 glass; }
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
    lifted = lift_main_part_glass_surface_single_tinted(source)
    for filename in (
        "main_part_projection_abi.hlsl", "main_part_perframe_abi.hlsl",
        "main_part_glass_abi.hlsl",
    ):
        assert f'#include "include/{filename}"' in lifted
    assert '#include "include/main_part_glass_surface_single.hlsl"' in lifted
    assert "Texture2D<float4> tDif" in lifted
    assert "void commonPS(" in lifted
    assert "partPositionState" not in lifted
