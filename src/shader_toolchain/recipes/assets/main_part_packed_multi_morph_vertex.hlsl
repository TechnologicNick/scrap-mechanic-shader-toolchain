#ifndef MAIN_PART_PACKED_MULTI_MORPH_VERTEX_HLSL
#define MAIN_PART_PACKED_MULTI_MORPH_VERTEX_HLSL

#include "main_part_packed_transform_vertex.hlsl"

// Common packed-frame backend after a deformation policy resolves local
// position and normal. Two- and three-pose frontends share this verbatim.
MainPartPackedTransformSurfaceVertex EvaluateMainPartPackedResolvedSurfaceVertex(
    float3 localPosition,
    float2 uv0,
    float2 uv1,
    float occlusion,
    float3 localNormal,
    float3 bitangentNormal,
    float4 tangentEncoded,
    int4 packedLocalToWorld,
    uint4 packedInstance,
    float cutoff)
{
  MainPartPackedTransformSurfaceVertex result;

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
  float3 planeWorldPosition = MainPartTransformPackedPoint(
      (float3)packedLocalToWorld.xyz * 0.125, transformIndex);
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
  float3 normalView = axisYView * localNormal.y;
  normalView = axisXView * localNormal.x + normalView;
  normalView = axisZView * localNormal.z + normalView;
  normalView *= rsqrt(dot(normalView, normalView));

  float3 localTangent = tangentEncoded.xyz * 2.0 - 1.0;
  float3 tangentView = axisYView * localTangent.y;
  tangentView = axisXView * localTangent.x + tangentView;
  tangentView = axisZView * localTangent.z + tangentView;
  tangentView *= rsqrt(dot(tangentView, tangentView));
  float tangentSign = tangentEncoded.w != 0.0 ? 1.0 : -1.0;
  float3 localBitangent = cross(bitangentNormal, localTangent) * tangentSign;
  float3 bitangentView = axisYView * localBitangent.y;
  bitangentView = axisXView * localBitangent.x + bitangentView;
  bitangentView = axisZView * localBitangent.z + bitangentView;
  bitangentView *= rsqrt(dot(bitangentView, bitangentView));

  float3 projected = clipPosition.xyz / clipPosition.w;
  projected = projected * float3(0.5, -0.5, 1.0)
      + float3(0.5, 0.5, 0.0);
  float viewDistance = sqrt(dot(viewPosition.xyz, viewPosition.xyz));
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
  result.fogColor = EvaluateMainPartVertexFog(viewDistance, worldPosition.z);
  result.cutoff = cutoff;
  return result;
}

MainPartPackedTransformSurfaceVertex EvaluateMainPartPackedDualMorphSurfaceVertex(
    float3 basePosition,
    float2 uv0,
    float2 uv1,
    float3 baseNormalEncoded,
    float4 tangentEncoded,
    float3 pose0Position,
    float3 pose0NormalEncoded,
    float3 pose1Position,
    float3 pose1NormalEncoded,
    int4 packedLocalToWorld,
    uint4 packedInstance)
{
  float pose0Weight = (float)(packedInstance.z & 65535u) / 65535.0;
  float pose1Weight = (float)(packedInstance.z >> 16u) / 65535.0;
  float3 localPosition = basePosition
      + (pose0Position - basePosition) * pose0Weight
      + (pose1Position - basePosition) * pose1Weight;
  float3 baseNormal = baseNormalEncoded * 2.0 - 1.0;
  float3 pose0Normal = pose0NormalEncoded * 2.0 - 1.0;
  float3 pose1Normal = pose1NormalEncoded * 2.0 - 1.0;
  float3 localNormal = baseNormal
      + (pose0Normal - baseNormal) * pose0Weight
      + (pose1Normal - baseNormal) * pose1Weight;
  float cutoff = (float)(packedInstance.w & 65535u) / 65535.0;
  return EvaluateMainPartPackedResolvedSurfaceVertex(
      localPosition, uv0, uv1, 0.0, localNormal, baseNormal,
      tangentEncoded, packedLocalToWorld, packedInstance, cutoff);
}

MainPartPackedTransformSurfaceVertex EvaluateMainPartPackedTripleMorphSurfaceVertex(
    float3 basePosition,
    float2 uv0,
    float2 uv1,
    float3 baseNormalEncoded,
    float4 tangentEncoded,
    float3 pose0Position,
    float3 pose0NormalEncoded,
    float3 pose1Position,
    float3 pose1NormalEncoded,
    float3 pose2Position,
    float3 pose2NormalEncoded,
    int4 packedLocalToWorld,
    uint4 packedInstance)
{
  float pose0Weight = (float)(packedInstance.z & 65535u) / 65535.0;
  float pose1Weight = (float)(packedInstance.z >> 16u) / 65535.0;
  float pose2Weight = (float)(packedInstance.w & 65535u) / 65535.0;
  float3 localPosition = basePosition
      + (pose0Position - basePosition) * pose0Weight
      + (pose1Position - basePosition) * pose1Weight
      + (pose2Position - basePosition) * pose2Weight;
  float3 baseNormal = baseNormalEncoded * 2.0 - 1.0;
  float3 pose0Normal = pose0NormalEncoded * 2.0 - 1.0;
  float3 pose1Normal = pose1NormalEncoded * 2.0 - 1.0;
  float3 pose2Normal = pose2NormalEncoded * 2.0 - 1.0;
  float3 localNormal = baseNormal
      + (pose0Normal - baseNormal) * pose0Weight
      + (pose1Normal - baseNormal) * pose1Weight
      + (pose2Normal - baseNormal) * pose2Weight;
  float cutoff = (float)(packedInstance.w >> 16u) / 65535.0;
  return EvaluateMainPartPackedResolvedSurfaceVertex(
      localPosition, uv0, uv1, 0.0, localNormal, baseNormal,
      tangentEncoded, packedLocalToWorld, packedInstance, cutoff);
}

#endif // MAIN_PART_PACKED_MULTI_MORPH_VERTEX_HLSL
