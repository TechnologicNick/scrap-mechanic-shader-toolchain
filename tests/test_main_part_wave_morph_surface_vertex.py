from shader_toolchain.recipes.main_part import (
    WAVE_MORPH_SURFACE_DEFINES,
    is_main_part_wave_morph_surface,
    lift_main_part_wave_morph_surface,
)


def test_wave_morph_surface_policy_is_exact() -> None:
    defines = sorted(WAVE_MORPH_SURFACE_DEFINES)
    assert is_main_part_wave_morph_surface(defines)
    assert not is_main_part_wave_morph_surface(
        [define for define in defines if define != "TRANSFER_NORMAL"]
    )
    assert not is_main_part_wave_morph_surface(
        defines + ["TRANSFER_TANGENTS"]
    )


def test_wave_morph_surface_lift_reuses_typed_layers() -> None:
    source = '''cbuffer CB_PROJECTION : register(b5) { float4 projection; }
cbuffer CB_PERFRAME : register(b12) { float4 perFrame; }
cbuffer CB_WAVE { float4 wave; }
// 3Dmigoto declarations
#define cmp -
void mainVS(
  float3 v0 : POSITION0, float2 v1 : TEXCOORD0,
  float3 v2 : NORMAL0, float3 v3 : POSITION1, float3 v4 : NORMAL1,
  float4 v5 : LTW0, float4 v6 : LTW1, float4 v7 : LTW2,
  uint4 v8 : INSTANCE_DATA0, out float4 o0 : SV_Position0,
  out float3 o1 : VIEW_POSITION0, out float2 o2 : UV0,
  out float3 o3 : NORMAL0, out float4 o4 : VERTEXCOLOR0,
  out float3 o5 : SCREEN_UV0) {}
'''
    lifted = lift_main_part_wave_morph_surface(source)
    for filename in (
        "main_part_projection_abi.hlsl",
        "main_part_perframe_abi.hlsl",
        "main_part_wave_abi.hlsl",
        "main_part_morph_vertex.hlsl",
        "main_part_scaled_wave_common.hlsl",
        "main_part_wave_morph_surface_vertex.hlsl",
    ):
        assert f'#include "include/{filename}"' in lifted
    assert "EvaluateMainPartWaveMorphSurfaceVertex" in lifted
    for assignment in ("o0 =", "o1 =", "o2 =", "o3 =", "o4 =", "o5 ="):
        assert assignment in lifted
    assert "partPositionState" not in lifted
