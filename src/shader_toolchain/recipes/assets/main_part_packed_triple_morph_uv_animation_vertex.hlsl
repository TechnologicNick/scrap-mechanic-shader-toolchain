#ifndef MAIN_PART_PACKED_TRIPLE_MORPH_UV_ANIMATION_VERTEX_HLSL
#define MAIN_PART_PACKED_TRIPLE_MORPH_UV_ANIMATION_VERTEX_HLSL

// Packed-LTW three-pose vertex with atlas animation and surface channels.
// The packed frame reconstruction is shared with this family through the
// canonical packed-axis transform helpers and the CB_UVFRAME ABI.

struct MainPartPackedTripleMorphUvAnimationVertex
{
  float4 clipPosition;
  float3 viewPosition;
  float2 uv0;
  float3 normalView;
  float4 color;
  float3 screenUv;
};

MainPartPackedTripleMorphUvAnimationVertex
EvaluateMainPartPackedTripleMorphUvAnimationVertex(
    float3 basePosition,
    float2 baseUv,
    float3 baseNormalEncoded,
    float3 pose0Position,
    float3 pose0NormalEncoded,
    float3 pose1Position,
    float3 pose1NormalEncoded,
    float3 pose2Position,
    float3 pose2NormalEncoded,
    int4 packedLocalToWorld,
    uint4 packedInstance)
{
  MainPartPackedTripleMorphUvAnimationVertex result;

  // Phase 1: decode pose weights, shake, color, and atlas frame.
  float pose0Weight = (float)(packedInstance.z & 65535u)
      * (1.0 / 65535.0);
  float pose1Weight = (float)(packedInstance.z >> 16u)
      * (1.0 / 65535.0);
  float pose2Weight = (float)(packedInstance.w & 65535u)
      * (1.0 / 65535.0);
  float shakeWeight = (float)(packedInstance.y >> 26u) * (1.0 / 63.0);
  uint frameIndex = packedInstance.w >> 16u;

  // Phase 2: accumulate three additive pose deltas.
  float3 localPosition = (pose0Position - basePosition) * pose0Weight
      + basePosition;
  localPosition = (pose1Position - basePosition) * pose1Weight
      + localPosition;
  localPosition = (pose2Position - basePosition) * pose2Weight
      + localPosition;

  // Phase 3: reconstruct the quantized local frame and world position.
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
  worldPosition += cb_vShake * shakeWeight;

  // Phase 4: preserve world -> view -> clip projection ordering.
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

  // Phase 5: map the packed frame index into the signed atlas convention.
  float columns = ceil(1.0 / uvAnimationFrame.x);
  float frameColumnCoordinate = frameIndex / columns;
  float signedColumn = frameColumnCoordinate >= -frameColumnCoordinate
      ? frac(abs(frameColumnCoordinate))
      : -frac(abs(frameColumnCoordinate));
  float row = floor((0.5 + frameIndex) / columns);
  float2 uv0 = uvAnimationFrame.xy * float2(signedColumn * columns, -row)
      + baseUv;

  // Phase 6: morph and transform the normal through the same packed frame.
  float3 baseNormal = baseNormalEncoded * 2.0 - 1.0;
  float3 pose0Normal = pose0NormalEncoded * 2.0 - 1.0;
  float3 pose1Normal = pose1NormalEncoded * 2.0 - 1.0;
  float3 pose2Normal = pose2NormalEncoded * 2.0 - 1.0;
  float3 localNormal = (pose0Normal - baseNormal) * pose0Weight
      + baseNormal;
  localNormal = (pose1Normal - baseNormal) * pose1Weight + localNormal;
  localNormal = (pose2Normal - baseNormal) * pose2Weight + localNormal;
  float3 axisYView = MainPartPackedHomogeneousToView(worldAxisY);
  float3 axisXView = MainPartPackedHomogeneousToView(worldAxisX);
  float3 axisZView = MainPartPackedHomogeneousToView(worldAxisZ);
  float3 normalView = axisYView * localNormal.y;
  normalView = axisXView * localNormal.x + normalView;
  normalView = axisZView * localNormal.z + normalView;
  normalView *= rsqrt(dot(normalView, normalView));

  float3 projected = clipPosition.xyz / clipPosition.w;
  projected = projected * float3(0.5, -0.5, 1.0)
      + float3(0.5, 0.5, 0.0);

  result.clipPosition = clipPosition;
  result.viewPosition = viewPosition.xyz;
  result.uv0 = uv0;
  result.normalView = normalView;
  result.color = float4(
      (packedInstance.x >> 24u) & 255u,
      (packedInstance.x >> 16u) & 255u,
      (packedInstance.x >> 8u) & 255u,
      packedInstance.x & 255u) * (1.0 / 255.0);
  result.screenUv = float3(cb_vRenderScale * projected.xy, projected.z);
  return result;
}

#endif // MAIN_PART_PACKED_TRIPLE_MORPH_UV_ANIMATION_VERTEX_HLSL

