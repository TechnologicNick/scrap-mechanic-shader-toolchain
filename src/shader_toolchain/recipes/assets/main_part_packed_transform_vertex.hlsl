// Shared packed-LTW morph vertex reconstruction.

#include "main_part_vertex_fog.hlsl"
//
// The packed LTW input stores a quantized translation and two axis codes. The
// missing axis is reconstructed with a cross product, after which CB_TRANSFORMS
// supplies the instance transform. This family is distinct from vertices that
// receive three explicit LTW rows but emits the same material-facing channels.

struct MainPartPackedTransformVertex
{
  float4 clipPosition;
  float3 viewPosition;
  float2 uv0;
  float2 uv1;
  float3 normalView;
  float4 color;
  float cutoff;
};

// Material-facing packed-LTW variant.  Some permutations consume the same
// compact transform and pose data but also require a complete tangent frame,
// vertex occlusion, and projected screen coordinates.
struct MainPartPackedTransformSurfaceVertex
{
  float4 clipPosition;
  float3 viewPosition;
  float occlusion;
  float2 uv0;
  float2 uv1;
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

static const float3 MAIN_PART_PACKED_AXES[6] =
{
  float3( 0.00,  0.00, -0.25),
  float3( 0.00, -0.25,  0.00),
  float3(-0.25,  0.00,  0.00),
  float3( 0.25,  0.00,  0.00),
  float3( 0.00,  0.25,  0.00),
  float3( 0.00,  0.00,  0.25),
};

float4 MainPartTransformPackedDirection(float3 direction, uint transformIndex)
{
  float4 transformed = transformArray[transformIndex]._m01_m11_m21_m31
      * direction.y;
  transformed = transformArray[transformIndex]._m00_m10_m20_m30
      * direction.x + transformed;
  transformed = transformArray[transformIndex]._m02_m12_m22_m32
      * direction.z + transformed;
  return transformed;
}

float3 MainPartTransformPackedPoint(float3 localPoint, uint transformIndex)
{
  float3 transformed = transformArray[transformIndex]._m01_m11_m21
      * localPoint.y;
  transformed = transformArray[transformIndex]._m00_m10_m20 * localPoint.x
      + transformed;
  transformed = transformArray[transformIndex]._m02_m12_m22 * localPoint.z
      + transformed;
  return transformArray[transformIndex]._m03_m13_m23 + transformed;
}

float3 MainPartPackedHomogeneousToView(float4 value)
{
  float3 transformed = worldToView._m01_m11_m21 * value.y;
  transformed = worldToView._m00_m10_m20 * value.x + transformed;
  transformed = worldToView._m02_m12_m22 * value.z + transformed;
  return worldToView._m03_m13_m23 * value.w + transformed;
}

MainPartPackedTransformVertex EvaluateMainPartPackedTransformVertex(
    float3 basePosition,
    float2 uv0,
    float2 uv1,
    float3 baseNormalEncoded,
    float3 morphPosition,
    float3 morphNormalEncoded,
    int4 packedLocalToWorld,
    uint4 packedInstance)
{
  MainPartPackedTransformVertex result;

  float morphWeight = (float)(packedInstance.z & 65535u) / 65535.0;
  float cutoff = (float)(packedInstance.w & 65535u) / 65535.0;
  float3 localPosition = (morphPosition - basePosition) * morphWeight
      + basePosition;

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

  float3 baseNormal = baseNormalEncoded * 2.0 - 1.0;
  float3 morphNormal = morphNormalEncoded * 2.0 - 1.0;
  float3 localNormal = (morphNormal - baseNormal) * morphWeight + baseNormal;
  float3 axisZView = MainPartPackedHomogeneousToView(worldAxisZ);
  float3 axisXView = MainPartPackedHomogeneousToView(worldAxisX);
  float3 axisYView = MainPartPackedHomogeneousToView(worldAxisY);
  float3 normalView = axisYView * localNormal.y;
  normalView = axisXView * localNormal.x + normalView;
  normalView = axisZView * localNormal.z + normalView;
  normalView *= rsqrt(dot(normalView, normalView));

  result.clipPosition = clipPosition;
  result.viewPosition = viewPosition.xyz;
  result.uv0 = uv0;
  result.uv1 = uv1;
  result.normalView = normalView;
  result.color = float4(
      (packedInstance.x >> 24u) & 255u,
      (packedInstance.x >> 16u) & 255u,
      (packedInstance.x >> 8u) & 255u,
      packedInstance.x & 255u) / 255.0;
  result.cutoff = cutoff;
  return result;
}

MainPartPackedTransformSurfaceVertex
EvaluateMainPartPackedTransformSurfaceVertex(
    float3 basePosition,
    float2 uv0,
    float2 uv1,
    float occlusion,
    float3 baseNormalEncoded,
    float4 tangentEncoded,
    float3 morphPosition,
    float3 morphNormalEncoded,
    int4 packedLocalToWorld,
    uint4 packedInstance)
{
  MainPartPackedTransformSurfaceVertex result;

  float morphWeight = (float)(packedInstance.z & 65535u) / 65535.0;
  float3 localPosition = (morphPosition - basePosition) * morphWeight
      + basePosition;

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

  float3 baseNormal = baseNormalEncoded * 2.0 - 1.0;
  float3 morphNormal = morphNormalEncoded * 2.0 - 1.0;
  float3 localNormal = (morphNormal - baseNormal) * morphWeight + baseNormal;
  float3 normalView = axisYView * localNormal.y;
  normalView = axisXView * localNormal.x + normalView;
  normalView = axisZView * localNormal.z + normalView;
  normalView *= rsqrt(dot(normalView, normalView));

  float3 localTangent = tangentEncoded.xyz * 2.0 - 1.0;
  float3 tangentView = axisYView * localTangent.y;
  tangentView = axisXView * localTangent.x + tangentView;
  tangentView = axisZView * localTangent.z + tangentView;
  tangentView *= rsqrt(dot(tangentView, tangentView));

  // The original permutation constructs this from the base normal, not the
  // interpolated pose normal.  Preserve that distinction as part of the ABI.
  float tangentSign = tangentEncoded.w != 0.0 ? 1.0 : -1.0;
  float3 localBitangent = cross(baseNormal, localTangent) * tangentSign;
  float3 bitangentView = axisYView * localBitangent.y;
  bitangentView = axisXView * localBitangent.x + bitangentView;
  bitangentView = axisZView * localBitangent.z + bitangentView;
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
  result.fogColor = EvaluateMainPartVertexFog(
      viewDistance, worldPosition.z);
  result.cutoff = (float)(packedInstance.w & 65535u) / 65535.0;
  return result;
}
