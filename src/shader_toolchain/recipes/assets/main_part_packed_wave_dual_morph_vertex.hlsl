// Packed-LTW no-scale wave vertex with two position poses and UV scrolling.

#include "main_part_wave_common.hlsl"

struct MainPartPackedWaveDualMorphVertex
{
  float4 clipPosition;
  float2 uv0;
  float2 uv1;
  float cutoff;
};

MainPartPackedWaveDualMorphVertex EvaluateMainPartPackedWaveDualMorphVertex(
    float3 basePosition,
    float2 uv0,
    float2 uv1,
    float3 normalEncoded,
    float3 pose0Position,
    float3 pose1Position,
    int4 packedLocalToWorld,
    uint4 packedInstance)
{
  MainPartPackedWaveDualMorphVertex result;

  float3 localPosition = MainPartApplyNoScaleWave(
      basePosition, normalEncoded);
  float pose0Weight = (float)(packedInstance.z & 65535u) * (1.0 / 65535.0);
  float pose1Weight = (float)(packedInstance.z >> 16u) * (1.0 / 65535.0);
  localPosition += (pose0Position - basePosition) * pose0Weight;
  localPosition += (pose1Position - basePosition) * pose1Weight;

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
  result.uv1 = uv1;
  result.cutoff = (float)(packedInstance.w & 65535u) * (1.0 / 65535.0);
  return result;
}
