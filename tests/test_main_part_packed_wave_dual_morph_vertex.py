from shader_toolchain.recipes.main_part import (
    PACKED_WAVE_DUAL_MORPH_UV_SCROLL_DEFINES,
    is_main_part_packed_wave_dual_morph_uv_scroll,
    lift_main_part_packed_wave_dual_morph_uv_scroll,
)


def test_packed_wave_dual_morph_policy_is_exact() -> None:
    defines = sorted(PACKED_WAVE_DUAL_MORPH_UV_SCROLL_DEFINES)
    assert is_main_part_packed_wave_dual_morph_uv_scroll(defines)
    assert not is_main_part_packed_wave_dual_morph_uv_scroll(
        [define for define in defines if define != "VS_POSE_1_ANIM"]
    )
    assert not is_main_part_packed_wave_dual_morph_uv_scroll(
        defines + ["TRANSFER_COLOR"]
    )


def test_packed_wave_dual_morph_lift_reuses_wave_and_transform_models() -> None:
    source = '''cbuffer CB_PROJECTION : register(b5) { float4 projection; }
cbuffer CB_PERFRAME : register(b12) { float4 perFrame; }
cbuffer CB_TRANSFORMS : register(b7) { float4 transforms; }
cbuffer CB_UV_SCROLL { float4 scroll; }
cbuffer CB_WAVE { float4 wave; }
// 3Dmigoto declarations
#define cmp -
void mainVS(
  float3 v0 : POSITION0, float4 v1 : TEXCOORD0,
  float2 v2 : TEXCOORD1, float3 v3 : NORMAL0,
  float4 v4 : TANGENT0, float3 v5 : POSITION1,
  float3 v6 : NORMAL1, float3 v7 : POSITION2,
  float3 v8 : NORMAL2, int4 v9 : LTWPACKED0,
  uint4 v10 : INSTANCE_DATA0, out float4 o0 : SV_Position0,
  out float2 o1 : UV0, out float2 p1 : UV1,
  out noperspective float o2 : CUTOFF0) {}
'''
    lifted = lift_main_part_packed_wave_dual_morph_uv_scroll(source)
    for filename in (
        "main_part_projection_abi.hlsl", "main_part_perframe_abi.hlsl",
        "main_part_transforms_abi.hlsl", "main_part_uv_scroll_abi.hlsl",
        "main_part_wave_abi.hlsl",
    ):
        assert f'#include "include/{filename}"' in lifted
    assert '#include "include/main_part_packed_transform_vertex.hlsl"' in lifted
    assert '#include "include/main_part_packed_wave_dual_morph_vertex.hlsl"' in lifted
    assert "EvaluateMainPartPackedWaveDualMorphVertex" in lifted
    assert "float2 v1 : TEXCOORD0" in lifted
    for assignment in ("o0 =", "o1 =", "p1 =", "o2 ="):
        assert assignment in lifted
    assert "partPositionState" not in lifted
