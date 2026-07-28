// Composition layer for permutations that emit AO, indirect, and SSS.
#include "indirect_cascade_upscale_bound.hlsl"
#include "indirect_cascade_upscale_indirect_bound.hlsl"

struct UpscaleFullSurface
{
  UpscaleSurface common;
  UpscaledIndirect indirect;
};

struct UpscaleFullTemporalResult
{
  float ao;
  float3 indirect;
  float4 sss;
  float cascadeVisibility;
};

struct FullSpatialAccumulator
{
  float4 coherentIndirectAo;
  float4 coherentSss;
  float coherentWeight;
  float4 sparseIndirectAo;
  float4 sparseSss;
  float sparseWeight;
};

void AccumulateFullFootprint(
    int2 samplePixel,
    float coherentBias,
    float centerDepth,
    float threshold,
    float inverseThreshold,
    float responseExponent,
    float edgeResponse,
    inout FullSpatialAccumulator accumulator)
{
  bool2 belowLimit = samplePixel < (int2)cb_vTargetSize.xy;
  bool insideTarget = belowLimit.y ? belowLimit.x : false;
  bool2 aboveOrigin = int2(0, 0) < samplePixel;
  bool afterOrigin = aboveOrigin.y ? aboveOrigin.x : false;
  if (!(insideTarget && afterOrigin))
    return;

  float2 gatherUv = float2(samplePixel) / cb_vTargetSize.xy;
  float2 halfPixel = cb_vRenderScale.xy * cb_vContainerPixelSize.xy;
  halfPixel = float2(0.5, 0.5) * halfPixel;
  gatherUv = gatherUv * cb_vRenderScale.xy + halfPixel;
  float4 depthError = GatherUpscaleDepthError(
      tAoDepth, LinearClampClamp_s, gatherUv, centerDepth);
  float4 accepted = depthError < threshold.xxxx;
  accepted = accepted ? float4(1.0, 1.0, 1.0, 1.0) : 0.0;
  float acceptedCount = dot(accepted, float4(1.0, 1.0, 1.0, 1.0));

  float2 sourceUv = cb_settings.vInvScale.xy * gatherUv;
  sourceUv = min(cb_settings.vUvLimit.xy, sourceUv);
  float4 indirectAo = tIndirect_Ao.SampleLevel(
      LinearClampClamp_s, sourceUv, 0.0);
  float4 sss = tSSS.SampleLevel(
      LinearClampClamp_s, sourceUv, 0.0);
  if (acceptedCount <= 3.0)
  {
    float weight = acceptedCount * 0.25 + 0.00999999978;
    accumulator.sparseIndirectAo =
        indirectAo * weight + accumulator.sparseIndirectAo;
    accumulator.sparseSss = sss * weight + accumulator.sparseSss;
    accumulator.sparseWeight = weight + accumulator.sparseWeight;
    return;
  }

  float gaussian = ComputeUpscaleGaussianWeight(
      depthError, inverseThreshold);
  float adjustedGaussian =
      edgeResponse * (coherentBias - gaussian) + gaussian;
  float coverage = ComputeUpscaleCoverageWeight(
      depthError, threshold, responseExponent);
  float weight = coverage * adjustedGaussian;
  accumulator.coherentIndirectAo =
      indirectAo * weight + accumulator.coherentIndirectAo;
  accumulator.coherentSss =
      sss * weight + accumulator.coherentSss;
  accumulator.coherentWeight = weight + accumulator.coherentWeight;
}

UpscaleFullSurface FilterBoundFullCross(int2 pixel, float centerDepth)
{
  UpscaleMaterialResponse material = EvaluateUpscaleMaterial(
      tMaterial.Load(int3(pixel, 0)).xy);
  float2 thresholdParameters =
      cb_f720To4K * float2(-0.0199999996, 8.0)
      + float2(0.0299999993, 4.0);
  float threshold = centerDepth * centerDepth;
  threshold = threshold * thresholdParameters.x;
  threshold = max(0.00999999978, threshold);
  threshold = min(0.5, threshold);
  threshold = threshold * threshold;
  float inverseThreshold = rcp(threshold);

  bool highResolution = 0.0 < cb_f720To4K;
  float jitterEnabled = highResolution ? 1.0 : 0.0;
  uint baseStride = highResolution ? 2u : 1u;
  uint phaseCount = (uint)(material.edgeResponse * -2.0 + 3.0);
  float depthJitter = 1.0 - saturate(0.25 * centerDepth);
  uint phase = asuint(cb_uFrameCount) % phaseCount;
  float jitter = depthJitter * float(phase);
  jitter = cb_fFrameRateScale * jitter;
  uint stride = (uint)(jitter * jitterEnabled + float(baseStride));
  float scaledRadius = cb_f720To4K * material.tapRadiusScale;
  scaledRadius = scaledRadius * 4.0 + 1.0;
  uint radius = (uint)(float(stride) * scaledRadius);

  FullSpatialAccumulator accumulated;
  accumulated.coherentIndirectAo = 0.0;
  accumulated.coherentSss = 0.0;
  accumulated.coherentWeight = 0.0;
  accumulated.sparseIndirectAo = 0.0;
  accumulated.sparseSss = 0.0;
  accumulated.sparseWeight = 0.0;
  AccumulateFullFootprint(pixel + int2(0, -int(radius)), 0.125,
      centerDepth, threshold, inverseThreshold, thresholdParameters.y,
      material.edgeResponse, accumulated);
  AccumulateFullFootprint(pixel + int2(-int(radius), 0), 0.125,
      centerDepth, threshold, inverseThreshold, thresholdParameters.y,
      material.edgeResponse, accumulated);
  AccumulateFullFootprint(pixel, 0.5,
      centerDepth, threshold, inverseThreshold, thresholdParameters.y,
      material.edgeResponse, accumulated);
  AccumulateFullFootprint(pixel + int2(int(radius), 0), 0.125,
      centerDepth, threshold, inverseThreshold, thresholdParameters.y,
      material.edgeResponse, accumulated);
  AccumulateFullFootprint(pixel + int2(0, int(radius)), 0.125,
      centerDepth, threshold, inverseThreshold, thresholdParameters.y,
      material.edgeResponse, accumulated);

  float4 fallbackIndirectAo = float4(
      0.125 * material.backgroundResponse.xxx, 1.0);
  if (material.edgeResponse * 0.0399999991 < accumulated.sparseWeight)
    fallbackIndirectAo =
        accumulated.sparseIndirectAo / accumulated.sparseWeight;
  float4 indirectAo = 0.0 < accumulated.coherentWeight
      ? accumulated.coherentIndirectAo / accumulated.coherentWeight
      : fallbackIndirectAo;
  float4 fallbackSss = 0.0 < accumulated.sparseWeight
      ? accumulated.sparseSss / accumulated.sparseWeight : 0.0;
  float4 sss = 0.0 < accumulated.coherentWeight
      ? accumulated.coherentSss / accumulated.coherentWeight : fallbackSss;

  UpscaleFullSurface result;
  result.common.pixel = pixel;
  result.common.viewDepth = centerDepth;
  result.common.ao = indirectAo.w;
  result.common.sss = sss;
  bool hasGeometry = centerDepth < UPSCALE_DEPTH_RANGE;
  result.common.sssComplement = hasGeometry ? 1.0 + -sss.x : 0.0;
  result.common.sssOcclusion = hasGeometry ? sss.x : 1.0;
  result.indirect.lighting = indirectAo.xyz;
  result.indirect.edgeResponse = material.edgeResponse;
  return result;
}

UpscaleFullSurface GatherBoundPerspectiveFullSurface(
    float2 unscaledUv, int2 pixel, float viewDepth)
{
  UpscaleFullSurface result = FilterBoundFullCross(pixel, viewDepth);
  float2 clipPosition =
      unscaledUv * float2(1.0, -1.0) + float2(0.0, 1.0);
  clipPosition =
      clipPosition * float2(2.0, 2.0) + float2(-1.0, -1.0);
  result.common.viewPosition.xy =
      cb_vNearFarViewCorner.zw * clipPosition;
  result.common.viewPosition.xy =
      result.common.viewPosition.xy * viewDepth.xx;
  result.common.viewPosition.z = -viewDepth;
  result.common.worldPosition = TransformUpscalePosition(
      viewToWorld, result.common.viewPosition);
  return result;
}

UpscaleFullSurface GatherBoundOrthoFullSurface(
    float2 unscaledUv, int2 pixel, float viewDepth)
{
  UpscaleFullSurface result = FilterBoundFullCross(pixel, viewDepth);
  UpscalePosition position =
      ReconstructOrthoUpscalePosition(unscaledUv, viewDepth);
  result.common.viewPosition = position.view;
  result.common.worldPosition = position.world;
  return result;
}

UpscaleCascadeLighting EvaluateBoundFullCascade(
    UpscaleFullSurface surface, bool mediumQuality)
{
  if (mediumQuality)
    return EvaluateBoundUpscaleCascadeLighting(surface.common);
  return EvaluateBoundLowUpscaleCascadeLighting(surface.common);
}

UpscaleFullTemporalResult ResolveBoundFullTemporalWithoutCascadeHistory(
    UpscaleFullSurface surface,
    UpscaleCascadeLighting cascade,
    float2 currentUv)
{
  UpscaleTemporalResult aoSss =
      ResolveBoundUpscaleTemporalWithoutCascadeHistory(
          surface.common, cascade, currentUv);
  float3 indirect = ResolveBoundIndirectTemporal(
      currentUv, surface.common.viewDepth,
      surface.common.worldPosition, surface.indirect);

  UpscaleFullTemporalResult result;
  result.ao = aoSss.ao;
  result.indirect = indirect;
  result.sss = aoSss.sss;
  // AO consumes the zero shadow response when no cascade lookup is needed,
  // while the final SSS clamp must retain fully visible light in that case.
  result.cascadeVisibility = cascade.visibility;
  return result;
}
