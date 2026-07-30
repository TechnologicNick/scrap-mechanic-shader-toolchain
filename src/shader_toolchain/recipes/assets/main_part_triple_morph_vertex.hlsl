// Shared three-pose extension of the explicit-LTW morph vertex family.

struct MainPartTripleMorphSurfaceVertex
{
  float4 clipPosition;
  float3 viewPosition;
  float2 uv0;
  float occlusion;
  float3 normalView;
  float3 tangentView;
  float3 bitangentView;
  float4 color;
  uint accentColor;
  float3 objectTangent;
  float3 screenUv;
  float3 worldPosition;
  float4 fogColor;
  float4 planeViewPosition;
  float cutoff;
};

MainPartTripleMorphSurfaceVertex EvaluateMainPartTripleMorphSurfaceVertex(
    float3 basePosition,
    float2 uv0,
    float occlusion,
    float3 baseNormalEncoded,
    float4 tangentEncoded,
    float3 morphPosition1,
    float3 morphNormalEncoded1,
    float3 morphPosition2,
    float3 morphNormalEncoded2,
    float3 morphPosition3,
    float3 morphNormalEncoded3,
    float4 localToWorldRow0,
    float4 localToWorldRow1,
    float4 localToWorldRow2,
    uint4 packedInstance)
{
  MainPartTripleMorphSurfaceVertex result;
  MainPartInstanceParameters instance = DecodeMainPartInstance(packedInstance);
  float morphWeight2 = (float)(packedInstance.z >> 16u) * (1.0 / 65535.0);
  float morphWeight3 = (float)(packedInstance.w & 65535u)
      * (1.0 / 65535.0);

  float3 localPosition = (morphPosition1 - basePosition)
      * instance.morphWeight + basePosition;
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

  float3 baseNormal = baseNormalEncoded * 2.0 - 1.0;
  float3 morphNormal1 = morphNormalEncoded1 * 2.0 - 1.0;
  float3 morphNormal2 = morphNormalEncoded2 * 2.0 - 1.0;
  float3 morphNormal3 = morphNormalEncoded3 * 2.0 - 1.0;
  float3 localNormal = (morphNormal1 - baseNormal)
      * instance.morphWeight + baseNormal;
  localNormal += (morphNormal2 - baseNormal) * morphWeight2;
  localNormal += (morphNormal3 - baseNormal) * morphWeight3;
  float3 localTangent = tangentEncoded.xyz * 2.0 - 1.0;
  float tangentSign = tangentEncoded.w != 0.0 ? 1.0 : -1.0;
  float3 localBitangent = cross(baseNormal, localTangent) * tangentSign;

  result.clipPosition = clipPosition;
  result.viewPosition = viewPosition.xyz;
  result.uv0 = uv0;
  result.occlusion = occlusion;
  result.normalView = NormalizeMainPartDirection(
      MainPartTransformLocalDirectionToView(
          localNormal, localToWorldRow0, localToWorldRow1, localToWorldRow2));
  result.tangentView = NormalizeMainPartDirection(
      MainPartTransformLocalDirectionToView(
          localTangent, localToWorldRow0, localToWorldRow1, localToWorldRow2));
  result.bitangentView = NormalizeMainPartDirection(
      MainPartTransformLocalDirectionToView(
          localBitangent, localToWorldRow0, localToWorldRow1,
          localToWorldRow2));
  result.color = instance.color;
  result.screenUv = clipPosition.xyz / clipPosition.w;
  result.screenUv = result.screenUv * float3(0.5, -0.5, 1.0)
      + float3(0.5, 0.5, 0.0);
  result.screenUv.xy *= cb_vRenderScale;
  result.worldPosition = worldPosition;
  float viewDistance = sqrt(dot(viewPosition.xyz, viewPosition.xyz));
  result.fogColor = EvaluateMainPartVertexFog(
      viewDistance, worldPosition.z);
  float3 planeWorldPosition = float3(
      localToWorldRow0.w, localToWorldRow1.w, localToWorldRow2.w);
  float3 planeViewPosition = worldToView._m01_m11_m21
      * planeWorldPosition.y;
  planeViewPosition = worldToView._m00_m10_m20
      * planeWorldPosition.x + planeViewPosition;
  planeViewPosition = worldToView._m02_m12_m22
      * planeWorldPosition.z + planeViewPosition;
  planeViewPosition += worldToView._m03_m13_m23;
  result.planeViewPosition = float4(planeViewPosition, 0.0);
  result.cutoff = (float)(packedInstance.w >> 16u) / 65535.0;
  return result;
}
