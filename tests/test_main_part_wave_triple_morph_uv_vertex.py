from shader_toolchain.recipes.main_part import (
    WAVE_TRIPLE_MORPH_UV_DEFINES,
    is_main_part_wave_triple_morph_uv,
    lift_main_part_wave_triple_morph_uv,
)


def test_wave_triple_morph_uv_policy_is_exact() -> None:
    defines = sorted(WAVE_TRIPLE_MORPH_UV_DEFINES)
    assert is_main_part_wave_triple_morph_uv(defines)
    assert not is_main_part_wave_triple_morph_uv(
        [define for define in defines if define != "VS_WAVE"]
    )
    assert not is_main_part_wave_triple_morph_uv(
        defines + ["TRANSFER_COLOR"]
    )


def test_wave_triple_morph_uv_reuses_shared_evaluator() -> None:
    source = '''cbuffer CB_PROJECTION : register(b5) { float4 projection; }
cbuffer CB_PERFRAME : register(b12) { float4 perFrame; }
cbuffer CB_WAVE { float4 wave; }
// 3Dmigoto declarations
#define cmp -
void mainVS(
  float3 v0 : POSITION0, float2 v1 : TEXCOORD0,
  float3 v2 : NORMAL0, float3 v3 : POSITION1,
  float3 v4 : NORMAL1, float3 v5 : POSITION2,
  float3 v6 : NORMAL2, float3 v7 : POSITION3,
  float3 v8 : NORMAL3, float4 v9 : LTW0,
  float4 v10 : LTW1, float4 v11 : LTW2,
  uint4 v12 : INSTANCE_DATA0, out float4 o0 : SV_Position0,
  out float2 o1 : UV0) {}
'''
    lifted = lift_main_part_wave_triple_morph_uv(source)
    for filename in (
        "main_part_projection_abi.hlsl",
        "main_part_perframe_abi.hlsl",
        "main_part_wave_abi.hlsl",
        "main_part_morph_vertex.hlsl",
        "main_part_wave_vertex.hlsl",
    ):
        assert f'#include "include/{filename}"' in lifted
    assert "EvaluateMainPartWaveVertex" in lifted
    assert "partPositionState" not in lifted

