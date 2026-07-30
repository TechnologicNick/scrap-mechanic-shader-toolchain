// Scale-aware wave, one pose delta, and explicit-LTW surface reconstruction.

struct MainPartWaveMorphSurfaceVertex
{
  float4 clipPosition;
  float3 viewPosition;
  float2 uv0;
  float3 normalView;
  float4 color;
  float3 screenUv;
};

MainPartWaveMorphSurfaceVertex EvaluateMainPartWaveMorphSurfaceVertex(
    float3 basePosition,
    float2 uv0,
    float3 baseNormalEncoded,
    float3 morphPosition,
    float3 morphNormalEncoded,
    float4 localToWorldRow0,
    float4 localToWorldRow1,
    float4 localToWorldRow2,
    uint4 packedInstance)
{
  MainPartWaveMorphSurfaceVertex result;
  MainPartInstanceParameters instance = DecodeMainPartInstance(packedInstance);

  float3 wavePosition = MainPartApplyScaledWave(
      basePosition, baseNormalEncoded,
      localToWorldRow0, localToWorldRow1, localToWorldRow2);
  float3 localPosition = (morphPosition - basePosition)
      * instance.morphWeight + wavePosition;
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

  float3 baseNormal = baseNormalEncoded * 2.0 - 1.0;
  float3 morphNormal = morphNormalEncoded * 2.0 - 1.0;
  float3 localNormal = (morphNormal - baseNormal)
      * instance.morphWeight + baseNormal;

  result.clipPosition = clipPosition;
  result.viewPosition = viewPosition.xyz;
  result.uv0 = uv0;
  result.normalView = NormalizeMainPartDirection(
      MainPartTransformLocalDirectionToView(
          localNormal, localToWorldRow0, localToWorldRow1, localToWorldRow2));
  result.color = instance.color;
  result.screenUv = clipPosition.xyz / clipPosition.w;
  result.screenUv = result.screenUv * float3(0.5, -0.5, 1.0)
      + float3(0.5, 0.5, 0.0);
  result.screenUv.xy *= cb_vRenderScale;
  return result;
}
