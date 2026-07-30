// Shared packed-transform vertex path for scrolling UV materials.

struct MainPartPackedUvScrollVertex
{
  float4 clipPosition;
  float2 uv0;
  float2 uv1;
  float3 screenUv;
  float cutoff;
};

MainPartPackedUvScrollVertex EvaluateMainPartPackedUvScrollVertex(
    float3 localPosition,
    float2 uv0,
    float2 uv1,
    int4 packedLocalToWorld,
    uint4 packedInstance)
{
  MainPartPackedUvScrollVertex result;

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

  float3 projected = clipPosition.xyz / clipPosition.w;
  projected = projected * float3(0.5, -0.5, 1.0)
      + float3(0.5, 0.5, 0.0);
  float2 scroll = frac(cb_uvScroll.vSpeed * cb_fTime);

  result.clipPosition = clipPosition;
  result.uv0 = uv0 + scroll;
  result.uv1 = uv1;
  result.screenUv = float3(cb_vRenderScale * projected.xy, projected.z);
  result.cutoff = (float)(packedInstance.w & 65535u) * (1.0 / 65535.0);
  return result;
}
