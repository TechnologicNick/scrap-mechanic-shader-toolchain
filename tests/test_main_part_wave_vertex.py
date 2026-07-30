from shader_toolchain.recipes.main_part import (
    WAVE_TRIPLE_MORPH_COLOR_DEFINES,
    is_main_part_wave_triple_morph_color,
    lift_main_part_wave_triple_morph_color,
)


def test_wave_triple_morph_policy_is_exact() -> None:
    defines = sorted(WAVE_TRIPLE_MORPH_COLOR_DEFINES)
    assert is_main_part_wave_triple_morph_color(defines)
    assert not is_main_part_wave_triple_morph_color(
        [define for define in defines if define != "VS_WAVE"]
    )
    assert not is_main_part_wave_triple_morph_color(
        defines + ["TRANSFER_NORMAL"]
    )


def test_wave_vertex_lift_reuses_explicit_ltw_instance_model() -> None:
    source = '''cbuffer CB_PROJECTION : register(b5) { float4 projection; }
cbuffer CB_PERFRAME : register(b12) { float4 perFrame; }
cbuffer CB_WAVE { float4 wave; }
// 3Dmigoto declarations
#define cmp -
void mainVS(
  float3 v0 : POSITION0, float2 v1 : TEXCOORD0, float3 v2 : NORMAL0,
  float3 v3 : POSITION1, float3 v4 : NORMAL1,
  float3 v5 : POSITION2, float3 v6 : NORMAL2,
  float3 v7 : POSITION3, float3 v8 : NORMAL3,
  float4 v9 : LTW0, float4 v10 : LTW1, float4 v11 : LTW2,
  uint4 v12 : INSTANCE_DATA0, out float4 o0 : SV_Position0,
  out float2 o1 : UV0, out float4 o2 : VERTEXCOLOR0) {}
'''
    lifted = lift_main_part_wave_triple_morph_color(source)
    for filename in (
        "main_part_projection_abi.hlsl", "main_part_perframe_abi.hlsl",
        "main_part_wave_abi.hlsl",
    ):
        assert f'#include "include/{filename}"' in lifted
    assert '#include "include/main_part_morph_vertex.hlsl"' in lifted
    assert '#include "include/main_part_wave_vertex.hlsl"' in lifted
    assert "EvaluateMainPartWaveVertex" in lifted
    for assignment in ("o0 =", "o1 =", "o2 ="):
        assert assignment in lifted
    assert "partPositionState" not in lifted
