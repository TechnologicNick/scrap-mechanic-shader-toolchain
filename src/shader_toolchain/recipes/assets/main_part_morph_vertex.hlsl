// Shared instanced morph/full-transform vertex reconstruction for main_part.

#include "main_part_vertex_fog.hlsl"

struct MainPartInstanceParameters
{
  float4 color;
  float morphWeight;
  float shakeWeight;
};

struct MainPartMorphVertex
{
  float4 clipPosition;
  float3 viewPosition;
  float2 uv0;
  float2 uv1;
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

MainPartInstanceParameters DecodeMainPartInstance(uint4 packedInstance)
{
  MainPartInstanceParameters instance;
  instance.color = float4(
      (packedInstance.x >> 24u) & 255u,
      (packedInstance.x >> 16u) & 255u,
      (packedInstance.x >> 8u) & 255u,
      packedInstance.x & 255u) * (1.0 / 255.0);
  instance.morphWeight = (float)(packedInstance.z & 65535u)
      * (1.0 / 65535.0);
  instance.shakeWeight = (float)(packedInstance.y >> 26u)
      * (1.0 / 63.0);
  return instance;
}

float3 MainPartTransformLocalDirectionToView(
    float3 localDirection,
    float4 localToWorldRow0,
    float4 localToWorldRow1,
    float4 localToWorldRow2)
{
  float3 localAxisY = float3(
      localToWorldRow0.y, localToWorldRow1.y, localToWorldRow2.y);
  float3 axisYView = worldToView._m01_m11_m21 * localAxisY.y;
  axisYView = worldToView._m00_m10_m20 * localAxisY.x + axisYView;
  axisYView = worldToView._m02_m12_m22 * localAxisY.z + axisYView;

  float3 localAxisX = float3(
      localToWorldRow0.x, localToWorldRow1.x, localToWorldRow2.x);
  float3 axisXView = worldToView._m01_m11_m21 * localAxisX.y;
  axisXView = worldToView._m00_m10_m20 * localAxisX.x + axisXView;
  axisXView = worldToView._m02_m12_m22 * localAxisX.z + axisXView;

  float3 localAxisZ = float3(
      localToWorldRow0.z, localToWorldRow1.z, localToWorldRow2.z);
  float3 axisZView = worldToView._m01_m11_m21 * localAxisZ.y;
  axisZView = worldToView._m00_m10_m20 * localAxisZ.x + axisZView;
  axisZView = worldToView._m02_m12_m22 * localAxisZ.z + axisZView;

  float3 directionView = axisYView * localDirection.y;
  directionView = axisXView * localDirection.x + directionView;
  directionView = axisZView * localDirection.z + directionView;
  return directionView;
}

float3 NormalizeMainPartDirection(float3 direction)
{
  return direction * rsqrt(dot(direction, direction));
}

MainPartMorphVertex EvaluateMainPartMorphVertex(
    float3 basePosition,
    float2 uv0,
    float2 uv1,
    float3 baseNormalEncoded,
    float4 tangentEncoded,
    float3 morphPosition,
    float3 morphNormalEncoded,
    float4 localToWorldRow0,
    float4 localToWorldRow1,
    float4 localToWorldRow2,
    uint4 packedInstance)
{
  MainPartMorphVertex result;
  MainPartInstanceParameters instance = DecodeMainPartInstance(packedInstance);

  float3 localPosition = (morphPosition - basePosition)
      * instance.morphWeight + basePosition;
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
  float3 localTangent = tangentEncoded.xyz * 2.0 - 1.0;
  float tangentSign = tangentEncoded.w != 0.0 ? 1.0 : -1.0;
  float3 localBitangent = cross(localNormal, localTangent) * tangentSign;

  result.clipPosition = clipPosition;
  result.viewPosition = viewPosition.xyz;
  result.uv0 = uv0;
  result.uv1 = uv1;
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
  result.cutoff = (float)(packedInstance.w & 65535u) * (1.0 / 65535.0);
  return result;
}
