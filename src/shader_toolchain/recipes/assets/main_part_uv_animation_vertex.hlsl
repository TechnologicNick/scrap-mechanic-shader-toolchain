#ifndef MAIN_PART_UV_ANIMATION_VERTEX_HLSL
#define MAIN_PART_UV_ANIMATION_VERTEX_HLSL

// Shared atlas phase. Geometry families call this after resolving their base
// UV, keeping VS_UV_ANIM independent from rigid/morph/transform selection.
float2 EvaluateMainPartAnimatedUv(float2 baseUv, uint packedFrameAndCutoff)
{
  uint frameIndex = packedFrameAndCutoff >> 16u;
  float columns = ceil(1.0 / uvAnimationFrame.x);
  float frameRowCoordinate = frameIndex / columns;
  float row = floor((frameIndex + 0.5) / columns);
  float signedFraction = frameRowCoordinate >= -frameRowCoordinate
      ? frac(abs(frameRowCoordinate)) : -frac(abs(frameRowCoordinate));
  float2 frame = float2(signedFraction * columns, -row);
  return uvAnimationFrame.xy * frame + baseUv;
}

// Shared semantic model for pose-0 part vertices with atlas UV animation.

struct MainPartUvAnimationVertex
{
  float4 clipPosition;
  float2 uv;
  float cutoff;
};

MainPartUvAnimationVertex EvaluateMainPartUvAnimationVertex(
    float3 basePosition,
    float2 baseUv,
    float3 posePosition,
    float4 localToWorldRow0,
    float4 localToWorldRow1,
    float4 localToWorldRow2,
    uint4 instanceData)
{
  float shakeWeight = (uint)(instanceData.y >> 26);
  shakeWeight *= 0.0158730168;
  float frameIndex = (uint)(instanceData.w >> 16);
  float poseWeight = (uint)(instanceData.z & 0xffff);
  float cutoff = (uint)(instanceData.w & 0xffff);
  poseWeight *= 1.52590219e-05;
  cutoff *= 1.52590219e-05;

  float3 localPosition = (posePosition - basePosition) * poseWeight
      + basePosition;
  float4 homogeneousPosition = float4(localPosition, 1.0);
  float3 worldPosition;
  worldPosition.x = dot(localToWorldRow0, homogeneousPosition);
  worldPosition.y = dot(localToWorldRow1, homogeneousPosition);
  worldPosition.z = dot(localToWorldRow2, homogeneousPosition);
  worldPosition += cb_vShake * shakeWeight;

  float4 viewPosition =
      worldToView._m01_m11_m21_m31 * worldPosition.y
      + worldToView._m00_m10_m20_m30 * worldPosition.x;
  viewPosition = worldToView._m02_m12_m22_m32 * worldPosition.z
      + viewPosition;
  viewPosition = worldToView._m03_m13_m23_m33 + viewPosition;
  float4 clipPosition =
      cb_xViewToProjection._m01_m11_m21_m31 * viewPosition.y
      + cb_xViewToProjection._m00_m10_m20_m30 * viewPosition.x;
  clipPosition = cb_xViewToProjection._m02_m12_m22_m32 * viewPosition.z
      + clipPosition;
  clipPosition = cb_xViewToProjection._m03_m13_m23_m33 * viewPosition.w
      + clipPosition;

  float columns = ceil(1.0 / uvAnimationFrame.x);
  float frameRowCoordinate = frameIndex / columns;
  float row = floor((frameIndex + 0.5) / columns);
  float signedFraction = frameRowCoordinate >= -frameRowCoordinate
      ? frac(abs(frameRowCoordinate)) : -frac(abs(frameRowCoordinate));
  float2 frame = float2(signedFraction * columns, -row);

  MainPartUvAnimationVertex result;
  result.clipPosition = clipPosition;
  result.uv = uvAnimationFrame.xy * frame + baseUv;
  result.cutoff = cutoff;
  return result;
}

#endif // MAIN_PART_UV_ANIMATION_VERTEX_HLSL
