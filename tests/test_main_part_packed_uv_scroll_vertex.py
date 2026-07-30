from shader_toolchain.recipes.main_part import (
    PACKED_UV_SCROLL_UV1_CUTOFF_DEFINES,
    is_main_part_packed_uv_scroll_uv1_cutoff,
    lift_main_part_packed_uv_scroll_uv1_cutoff,
)


def test_packed_uv_scroll_policy_is_exact() -> None:
    defines = sorted(PACKED_UV_SCROLL_UV1_CUTOFF_DEFINES)
    assert is_main_part_packed_uv_scroll_uv1_cutoff(defines)
    assert not is_main_part_packed_uv_scroll_uv1_cutoff(
        [define for define in defines if define != "VS_UV0_SCROLL"]
    )
    assert not is_main_part_packed_uv_scroll_uv1_cutoff(
        defines + ["TRANSFER_NORMAL"]
    )


def test_packed_uv_scroll_lift_reuses_packed_transform_model() -> None:
    source = '''cbuffer CB_PROJECTION : register(b5) { float4 projection; }
cbuffer CB_PERFRAME : register(b12) { float4 perFrame; }
cbuffer CB_TRANSFORMS : register(b7) { float4 transforms; }
cbuffer CB_UV_SCROLL { float4 scroll; }
// 3Dmigoto declarations
#define cmp -
void mainVS(
  float3 v0 : POSITION0, float4 v1 : TEXCOORD0,
  float2 v2 : TEXCOORD1, float3 v3 : NORMAL0,
  float4 v4 : TANGENT0, int4 v5 : LTWPACKED0,
  uint4 v6 : INSTANCE_DATA0, out float4 o0 : SV_Position0,
  out float2 o1 : UV0, out float2 p1 : UV1,
  out float3 o2 : SCREEN_UV0,
  out noperspective float o3 : CUTOFF0) {}
'''
    lifted = lift_main_part_packed_uv_scroll_uv1_cutoff(source)
    for filename in (
        "main_part_projection_abi.hlsl", "main_part_perframe_abi.hlsl",
        "main_part_transforms_abi.hlsl", "main_part_uv_scroll_abi.hlsl",
    ):
        assert f'#include "include/{filename}"' in lifted
    assert '#include "include/main_part_packed_transform_vertex.hlsl"' in lifted
    assert '#include "include/main_part_packed_uv_scroll_vertex.hlsl"' in lifted
    assert "float2 v1 : TEXCOORD0" in lifted
    assert "EvaluateMainPartPackedUvScrollVertex" in lifted
    for assignment in ("o0 =", "o1 =", "p1 =", "o2 =", "o3 ="):
        assert assignment in lifted
    assert "partPositionState" not in lifted
