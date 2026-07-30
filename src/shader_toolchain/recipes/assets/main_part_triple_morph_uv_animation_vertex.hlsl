#ifndef MAIN_PART_TRIPLE_MORPH_UV_ANIMATION_VERTEX_HLSL
#define MAIN_PART_TRIPLE_MORPH_UV_ANIMATION_VERTEX_HLSL

// Shared three-pose explicit-LTW geometry and atlas-animation core.
// Richer siblings can reuse this result before adding normals, colors, screen
// coordinates, wave deformation, or picking channels.

struct MainPartTripleMorphUvAnimationVertex
{
  float4 clipPosition;
  float2 uv0;
};

MainPartTripleMorphUvAnimationVertex
EvaluateMainPartTripleMorphUvAnimationVertex(
    float3 basePosition,
    float2 baseUv,
    float3 morphPosition1,
    float3 morphPosition2,
    float3 morphPosition3,
    float4 localToWorldRow0,
    float4 localToWorldRow1,
    float4 localToWorldRow2,
    uint4 packedInstance)
{
  // Phase 1: decode three additive pose weights, shake, and atlas frame.
  float morphWeight1 = (uint)(packedInstance.z & 0xffffu);
  float morphWeight2 = (uint)(packedInstance.z >> 16u);
  float morphWeight3 = (uint)(packedInstance.w & 0xffffu);
  morphWeight1 = 1.52590219e-05 * morphWeight1;
  morphWeight2 = 1.52590219e-05 * morphWeight2;
  morphWeight3 = 1.52590219e-05 * morphWeight3;
  float shakeWeight = (uint)(packedInstance.y >> 26u);
  uint frameIndex = (uint)(packedInstance.w >> 16u);

  // Phase 2: accumulate poses in the original additive order.
  float3 localPosition = (morphPosition1 - basePosition)
      * morphWeight1 + basePosition;
  localPosition = (morphPosition2 - basePosition)
      * morphWeight2 + localPosition;
  localPosition = (morphPosition3 - basePosition)
      * morphWeight3 + localPosition;
  float4 homogeneousPosition = float4(localPosition, 1);
  float3 worldPosition;
  worldPosition.x = dot(localToWorldRow0, homogeneousPosition);
  worldPosition.y = dot(localToWorldRow1, homogeneousPosition);
  worldPosition.z = dot(localToWorldRow2, homogeneousPosition);
  shakeWeight = 0.0158730168 * shakeWeight;
  worldPosition = cb_vShake * shakeWeight + worldPosition;

  // Phase 3: preserve the explicit world-to-view-to-projection ordering.
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

  // Phase 4: map the packed frame index into the signed atlas convention.
  float columns = 1 / uvAnimationFrame.x;
  columns = ceil(columns);
  float frameRowCoordinate = frameIndex / columns;
  float row = (0.5 + frameIndex) / columns;
  row = floor(row);
  float signedFraction = frameRowCoordinate >= -frameRowCoordinate
      ? frac(abs(frameRowCoordinate))
      : -frac(abs(frameRowCoordinate));
  float2 frame = float2(signedFraction * columns, -row);

  MainPartTripleMorphUvAnimationVertex result;
  result.clipPosition = clipPosition;
  result.uv0 = uvAnimationFrame.xy * frame + baseUv;
  return result;
}

#endif // MAIN_PART_TRIPLE_MORPH_UV_ANIMATION_VERTEX_HLSL
