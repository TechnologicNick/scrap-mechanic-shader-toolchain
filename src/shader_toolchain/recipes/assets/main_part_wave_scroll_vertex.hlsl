// Explicit-LTW no-scale wave vertex with UV scrolling and screen coordinates.

struct MainPartWaveScrollVertex
{
  float4 clipPosition;
  float2 uv0;
  float3 screenUv;
};

MainPartWaveScrollVertex EvaluateMainPartWaveScrollVertex(
    float3 basePosition,
    float2 uv0,
    float3 normalEncoded,
    float4 localToWorldRow0,
    float4 localToWorldRow1,
    float4 localToWorldRow2,
    uint4 packedInstance)
{
  MainPartWaveScrollVertex result;

  float shakeWeight = (float)(packedInstance.y >> 26u) / 63.0;
  float3 localPosition = MainPartApplyNoScaleWave(
      basePosition, normalEncoded);
  float4 homogeneousPosition = float4(localPosition, 1.0);
  float3 worldPosition = float3(
      dot(localToWorldRow0, homogeneousPosition),
      dot(localToWorldRow1, homogeneousPosition),
      dot(localToWorldRow2, homogeneousPosition));
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
  float2 uvOffset = frac(cb_uvScroll.vSpeed * cb_fTime);

  result.clipPosition = clipPosition;
  result.uv0 = uv0 + uvOffset;
  result.screenUv = float3(cb_vRenderScale * projected.xy, projected.z);
  return result;
}
