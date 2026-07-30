// Packed-LTW vertex path with no-scale wave deformation, UV scrolling, and
// picking-buffer color selection.

#include "main_part_wave_common.hlsl"

struct MainPartPackedWavePickingVertex
{
  float4 clipPosition;
  float2 uv0;
  float4 color;
};

#include "main_part_picking_common.hlsl"

MainPartPackedWavePickingVertex EvaluateMainPartPackedWavePickingVertex(
    float3 basePosition,
    float2 uv0,
    float3 normalEncoded,
    int4 packedLocalToWorld,
    uint4 packedInstance)
{
  MainPartPackedWavePickingVertex result;

  float3 localPosition = MainPartApplyNoScaleWave(
      basePosition, normalEncoded);

  uint axisZIndex = ((uint)packedLocalToWorld.w >> 4u) & 15u;
  uint axisXIndex = (uint)packedLocalToWorld.w & 15u;
  float3 axisZ = MAIN_PART_PACKED_AXES[axisZIndex];
  float3 axisX = MAIN_PART_PACKED_AXES[axisXIndex];
  float3 axisY = cross(axisZ, axisX);
  axisY *= rsqrt(dot(axisY, axisY));
  axisY *= 0.25;

  uint transformIndex = packedInstance.y & 1023u;
  float4 worldAxisY = MainPartTransformPackedDirection(axisY, transformIndex);
  float4 worldAxisX = MainPartTransformPackedDirection(axisX, transformIndex);
  float4 worldAxisZ = MainPartTransformPackedDirection(axisZ, transformIndex);
  float3 worldPosition = worldAxisY.xyz * localPosition.y;
  worldPosition = worldAxisX.xyz * localPosition.x + worldPosition;
  worldPosition = worldAxisZ.xyz * localPosition.z + worldPosition;
  float3 quantizedTranslation = (float3)packedLocalToWorld.xyz * 0.125;
  worldPosition += MainPartTransformPackedPoint(
      quantizedTranslation, transformIndex);

  float shakeWeight = (float)(packedInstance.y >> 26u) * (1.0 / 63.0);
  worldPosition += cb_vShake * shakeWeight;
  float4 viewPosition = worldToView._m01_m11_m21_m31 * worldPosition.y;
  viewPosition = worldToView._m00_m10_m20_m30 * worldPosition.x
      + viewPosition;
  viewPosition = worldToView._m02_m12_m22_m32 * worldPosition.z
      + viewPosition;
  viewPosition = worldToView._m03_m13_m23_m33 + viewPosition;
  float4 clipPosition = cb_xViewToProjection._m01_m11_m21_m31
      * viewPosition.y;
  clipPosition = cb_xViewToProjection._m00_m10_m20_m30
      * viewPosition.x + clipPosition;
  clipPosition = cb_xViewToProjection._m02_m12_m22_m32
      * viewPosition.z + clipPosition;
  clipPosition = cb_xViewToProjection._m03_m13_m23_m33
      * viewPosition.w + clipPosition;

  result.clipPosition = clipPosition;
  result.uv0 = uv0 + frac(cb_uvScroll.vSpeed * cb_fTime);
  result.color = MainPartDecodePickingColor(packedInstance.y);
  return result;
}
