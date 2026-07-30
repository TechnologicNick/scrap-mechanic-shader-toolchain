// Shared wave-deformed explicit-LTW vertex reconstruction.

struct MainPartWaveVertex
{
  float4 clipPosition;
  float2 uv0;
  float4 color;
};

MainPartWaveVertex EvaluateMainPartWaveVertex(
    float3 basePosition,
    float2 uv0,
    float3 baseNormalEncoded,
    float3 morphPosition1,
    float3 morphPosition2,
    float3 morphPosition3,
    float4 localToWorldRow0,
    float4 localToWorldRow1,
    float4 localToWorldRow2,
    uint4 packedInstance)
{
  MainPartWaveVertex result;
  MainPartInstanceParameters instance = DecodeMainPartInstance(packedInstance);
  float morphWeight2 = (float)(packedInstance.z >> 16u) * (1.0 / 65535.0);
  float morphWeight3 = (float)(packedInstance.w & 65535u)
      * (1.0 / 65535.0);

  float timePhase = cb_wave.fSpeed * cb_fTime;
  float3 phase = float3(13.5, 10.0, 7.0) * timePhase;
  const float3 diagonal = float3(
      0.577350259, 0.577350259, 0.577350259);
  float3 transformedDiagonal = float3(
      dot(localToWorldRow0.xyz, diagonal),
      dot(localToWorldRow1.xyz, diagonal),
      dot(localToWorldRow2.xyz, diagonal));
  float waveScale = sqrt(dot(transformedDiagonal, transformedDiagonal));
  phase += basePosition * waveScale * float3(63.0, 51.0, 124.0);
  float3 oscillation = float3(sin(phase.x), cos(phase.y), sin(phase.z));
  oscillation *= waveScale;
  float displacement = oscillation.x * 0.125;
  displacement += oscillation.y * 0.0920000002;
  displacement += oscillation.z * 0.103;
  displacement *= cb_wave.fStrength;

  float3 baseNormal = baseNormalEncoded * 2.0 - 1.0;
  float3 localPosition = basePosition + baseNormal * displacement;
  localPosition += (morphPosition1 - basePosition) * instance.morphWeight;
  localPosition += (morphPosition2 - basePosition) * morphWeight2;
  localPosition += (morphPosition3 - basePosition) * morphWeight3;

  float4 homogeneousPosition = float4(localPosition, 1.0);
  float3 worldPosition = float3(
      dot(localToWorldRow0, homogeneousPosition),
      dot(localToWorldRow1, homogeneousPosition),
      dot(localToWorldRow2, homogeneousPosition));
  worldPosition += cb_vShake * instance.shakeWeight;
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
  result.uv0 = uv0;
  result.color = instance.color;
  return result;
}
