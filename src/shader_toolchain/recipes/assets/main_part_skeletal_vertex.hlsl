#ifndef MAIN_PART_SKELETAL_VERTEX_HLSL
#define MAIN_PART_SKELETAL_VERTEX_HLSL

#include "main_part_packed_transform_vertex.hlsl"

// Four-weight character skinning composed with the packed instance frame.
// Bone matrices move mesh data into part-local space; LTWPACKED0 and
// INSTANCE_DATA0 then place that skinned part in the world exactly like the
// non-skeletal packed-transform families.

float3 MainPartSkinPoint(float3 sourcePosition, uint boneIndex)
{
  float3 transformed = xBones[boneIndex]._m01_m11_m21 * sourcePosition.y;
  transformed = xBones[boneIndex]._m00_m10_m20 * sourcePosition.x + transformed;
  transformed = xBones[boneIndex]._m02_m12_m22 * sourcePosition.z + transformed;
  return xBones[boneIndex]._m03_m13_m23 + transformed;
}

float3 MainPartSkinDirection(float3 direction, uint boneIndex)
{
  float3 transformed = xBones[boneIndex]._m01_m11_m21 * direction.y;
  transformed = xBones[boneIndex]._m00_m10_m20 * direction.x + transformed;
  transformed = xBones[boneIndex]._m02_m12_m22 * direction.z + transformed;
  return transformed;
}

float3 MainPartBlendSkinnedPoint(
    float3 sourcePosition, uint4 boneIndices, float4 boneWeights)
{
  float3 skinned = MainPartSkinPoint(
      sourcePosition, boneIndices.y) * boneWeights.y;
  skinned += MainPartSkinPoint(sourcePosition, boneIndices.x) * boneWeights.x;
  skinned += MainPartSkinPoint(sourcePosition, boneIndices.z) * boneWeights.z;
  skinned += MainPartSkinPoint(sourcePosition, boneIndices.w) * boneWeights.w;
  return skinned;
}

float3 MainPartBlendSkinnedDirection(
    float3 direction, uint4 boneIndices, float4 boneWeights)
{
  float3 skinned = MainPartSkinDirection(
      direction, boneIndices.y) * boneWeights.y;
  skinned += MainPartSkinDirection(
      direction, boneIndices.x) * boneWeights.x;
  skinned += MainPartSkinDirection(
      direction, boneIndices.z) * boneWeights.z;
  skinned += MainPartSkinDirection(
      direction, boneIndices.w) * boneWeights.w;
  return skinned;
}

float3 MainPartPackedFrameToView(
    float3 direction,
    float3 axisXView,
    float3 axisYView,
    float3 axisZView)
{
  float3 transformed = axisYView * direction.y;
  transformed = axisXView * direction.x + transformed;
  transformed = axisZView * direction.z + transformed;
  return transformed;
}

MainPartPackedTransformSurfaceVertex EvaluateMainPartSkeletalSurfaceVertex(
    float3 position,
    float2 uv0,
    float2 uv1,
    float occlusion,
    float3 normalEncoded,
    float4 tangentEncoded,
    uint4 boneIndices,
    float4 boneWeights,
    int4 packedLocalToWorld,
    uint4 packedInstance)
{
  MainPartPackedTransformSurfaceVertex result;

  uint boneBase = (packedInstance.y >> 16u) & 1023u;
  boneIndices += boneBase;

  float3 skinnedPosition = MainPartBlendSkinnedPoint(
      position, boneIndices, boneWeights);

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

  float3 worldPosition = worldAxisY.xyz * skinnedPosition.y;
  worldPosition = worldAxisX.xyz * skinnedPosition.x + worldPosition;
  worldPosition = worldAxisZ.xyz * skinnedPosition.z + worldPosition;
  float3 quantizedTranslation = (float3)packedLocalToWorld.xyz * 0.125;
  float3 planeWorldPosition = MainPartTransformPackedPoint(
      quantizedTranslation, transformIndex);
  worldPosition += planeWorldPosition;

  float shakeWeight = (float)(packedInstance.y >> 26u) / 63.0;
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

  float3 axisZView = MainPartPackedHomogeneousToView(worldAxisZ);
  float3 axisXView = MainPartPackedHomogeneousToView(worldAxisX);
  float3 axisYView = MainPartPackedHomogeneousToView(worldAxisY);

  float3 localNormal = normalEncoded * 2.0 - 1.0;
  float3 skinnedNormal = MainPartBlendSkinnedDirection(
      localNormal, boneIndices, boneWeights);
  float3 normalView = MainPartPackedFrameToView(
      skinnedNormal, axisXView, axisYView, axisZView);
  normalView *= rsqrt(dot(normalView, normalView));

  float3 localTangent = tangentEncoded.xyz * 2.0 - 1.0;
  float3 skinnedTangent = MainPartBlendSkinnedDirection(
      localTangent, boneIndices, boneWeights);
  float3 tangentView = MainPartPackedFrameToView(
      skinnedTangent, axisXView, axisYView, axisZView);
  tangentView *= rsqrt(dot(tangentView, tangentView));

  float tangentSign = tangentEncoded.w != 0.0 ? 1.0 : -1.0;
  float3 localBitangent = cross(localNormal, localTangent) * tangentSign;
  float3 skinnedBitangent = MainPartBlendSkinnedDirection(
      localBitangent, boneIndices, boneWeights);
  float3 bitangentView = MainPartPackedFrameToView(
      skinnedBitangent, axisXView, axisYView, axisZView);
  bitangentView *= rsqrt(dot(bitangentView, bitangentView));

  float3 projected = clipPosition.xyz / clipPosition.w;
  projected = projected * float3(0.5, -0.5, 1.0)
      + float3(0.5, 0.5, 0.0);

  result.clipPosition = clipPosition;
  result.viewPosition = viewPosition.xyz;
  result.occlusion = occlusion;
  result.uv0 = uv0;
  result.uv1 = uv1;
  result.normalView = normalView;
  result.tangentView = tangentView;
  result.bitangentView = bitangentView;
  result.color = float4(
      (packedInstance.x >> 24u) & 255u,
      (packedInstance.x >> 16u) & 255u,
      (packedInstance.x >> 8u) & 255u,
      packedInstance.x & 255u) / 255.0;
  result.screenUv = float3(cb_vRenderScale * projected.xy, projected.z);
  result.worldPosition = worldPosition;
  float3 planeViewPosition = worldToView._m01_m11_m21
      * planeWorldPosition.y;
  planeViewPosition = worldToView._m00_m10_m20
      * planeWorldPosition.x + planeViewPosition;
  planeViewPosition = worldToView._m02_m12_m22
      * planeWorldPosition.z + planeViewPosition;
  planeViewPosition += worldToView._m03_m13_m23;
  result.planeViewPosition = float4(planeViewPosition, 0.0);
  float viewDistance = sqrt(dot(viewPosition.xyz, viewPosition.xyz));
  result.fogColor = EvaluateMainPartVertexFog(viewDistance, worldPosition.z);
  result.cutoff = (float)(packedInstance.w & 65535u) / 65535.0;
  return result;
}

#endif // MAIN_PART_SKELETAL_VERTEX_HLSL
