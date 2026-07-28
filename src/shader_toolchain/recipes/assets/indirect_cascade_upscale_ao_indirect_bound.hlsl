// Bound helpers for permutations that jointly filter packed indirect RGB/AO.
#include "indirect_cascade_upscale_indirect_bound.hlsl"

struct UpscaleAoIndirectSurface
{
  int2 pixel;
  float viewDepth;
  float3 viewPosition;
  float3 worldPosition;
  float ao;
  UpscaledIndirect indirect;
};

struct AoIndirectAccumulator
{
  float4 coherent;
  float coherentWeight;
  float4 sparse;
  float sparseWeight;
};

void AccumulateAoIndirectFootprint(
    int2 samplePixel,
    float coherentBias,
    float centerDepth,
    float threshold,
    float inverseThreshold,
    float responseExponent,
    float edgeResponse,
    inout AoIndirectAccumulator accumulator)
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
  float gaussian = ComputeUpscaleGaussianWeight(
      depthError, inverseThreshold);
  float4 accepted = depthError < threshold.xxxx;
  accepted = accepted ? float4(1.0, 1.0, 1.0, 1.0) : 0.0;
  float acceptedCount = dot(accepted, float4(1.0, 1.0, 1.0, 1.0));
  float adjustedGaussian =
      edgeResponse * (coherentBias - gaussian) + gaussian;

  float2 sourceUv = cb_settings.vInvScale.xy * gatherUv;
  sourceUv = min(cb_settings.vUvLimit.xy, sourceUv);
  float4 indirectAo = tIndirect_Ao.SampleLevel(
      LinearClampClamp_s, sourceUv, 0.0);
  float coverage = ComputeUpscaleCoverageWeight(
      depthError, threshold, responseExponent);

  if (acceptedCount <= 3.0)
  {
    float weight = acceptedCount * 0.25 + 0.00999999978;
    accumulator.sparse = indirectAo * weight + accumulator.sparse;
    accumulator.sparseWeight = weight + accumulator.sparseWeight;
  }
  else
  {
    float weight = coverage * adjustedGaussian;
    accumulator.coherent = indirectAo * weight + accumulator.coherent;
    accumulator.coherentWeight = weight + accumulator.coherentWeight;
  }
}

UpscaleAoIndirectSurface FilterBoundAoIndirectCross(
    int2 pixel, float centerDepth)
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

  AoIndirectAccumulator accumulated;
  accumulated.coherent = 0.0;
  accumulated.coherentWeight = 0.0;
  accumulated.sparse = 0.0;
  accumulated.sparseWeight = 0.0;
  AccumulateAoIndirectFootprint(pixel + int2(0, -int(radius)), 0.125,
      centerDepth, threshold, inverseThreshold, thresholdParameters.y,
      material.edgeResponse, accumulated);
  AccumulateAoIndirectFootprint(pixel + int2(-int(radius), 0), 0.125,
      centerDepth, threshold, inverseThreshold, thresholdParameters.y,
      material.edgeResponse, accumulated);
  AccumulateAoIndirectFootprint(pixel, 0.5,
      centerDepth, threshold, inverseThreshold, thresholdParameters.y,
      material.edgeResponse, accumulated);
  AccumulateAoIndirectFootprint(pixel + int2(int(radius), 0), 0.125,
      centerDepth, threshold, inverseThreshold, thresholdParameters.y,
      material.edgeResponse, accumulated);
  AccumulateAoIndirectFootprint(pixel + int2(0, int(radius)), 0.125,
      centerDepth, threshold, inverseThreshold, thresholdParameters.y,
      material.edgeResponse, accumulated);

  float4 fallback = float4(
      0.125 * material.backgroundResponse.xxx, 1.0);
  if (material.edgeResponse * 0.0399999991 < accumulated.sparseWeight)
    fallback = accumulated.sparse / accumulated.sparseWeight;
  float4 indirectAo = 0.0 < accumulated.coherentWeight
      ? accumulated.coherent / accumulated.coherentWeight : fallback;

  UpscaleAoIndirectSurface result;
  result.pixel = pixel;
  result.viewDepth = centerDepth;
  result.ao = indirectAo.w;
  result.indirect.lighting = indirectAo.xyz;
  result.indirect.edgeResponse = material.edgeResponse;
  return result;
}

UpscaleAoIndirectSurface GatherBoundPerspectiveAoIndirectSurface(
    float2 unscaledUv, int2 pixel, float viewDepth)
{
  UpscaleAoIndirectSurface result =
      FilterBoundAoIndirectCross(pixel, viewDepth);
  float2 clipPosition =
      unscaledUv * float2(1.0, -1.0) + float2(0.0, 1.0);
  clipPosition = clipPosition * float2(2.0, 2.0)
      + float2(-1.0, -1.0);
  result.viewPosition.xy = cb_vNearFarViewCorner.zw * clipPosition;
  result.viewPosition.xy = result.viewPosition.xy * viewDepth.xx;
  result.viewPosition.z = -viewDepth;
  result.worldPosition = TransformUpscalePosition(
      viewToWorld, result.viewPosition);
  return result;
}

UpscaleAoIndirectSurface GatherBoundOrthoAoIndirectSurface(
    float2 unscaledUv, int2 pixel, float viewDepth)
{
  UpscaleAoIndirectSurface result =
      FilterBoundAoIndirectCross(pixel, viewDepth);
  float2 clipPosition =
      unscaledUv * float2(1.0, -1.0) + float2(0.0, 1.0);
  clipPosition = clipPosition * float2(2.0, 2.0)
      + float2(-1.0, -1.0);
  result.viewPosition.xy =
      cb_vNearFarViewCorner.zw * clipPosition + cb_vViewTranslate.xy;
  result.viewPosition.z = -viewDepth;
  result.worldPosition = TransformUpscalePosition(
      viewToWorld, result.viewPosition);
  return result;
}

float2 ResolveBoundAoIndirectTemporal(
    float2 currentUv,
    UpscaleAoIndirectSurface surface,
    float auxiliaryResponse)
{
  float2 current = float2(surface.ao, 1.0);
  float3 previousClip = ProjectUpscalePosition(
      cb_xPrevWorldToViewProjection, surface.worldPosition);
  float2 insidePrevious = abs(previousClip.xy) < previousClip.zz;
  if (!(insidePrevious.x && insidePrevious.y))
    return current;

  float viewDistance = sqrt(dot(
      surface.viewPosition, surface.viewPosition));
  float2 previousUv = previousClip.xy / previousClip.zz;
  previousUv = previousUv * float2(0.5, -0.5)
      + float2(0.5, 0.5);
  previousUv = cb_vPrevRenderScale.xy * previousUv;
  float nearDepthWeight = saturate(
      4.0 * (-0.800000012 + surface.viewDepth));
  nearDepthWeight = nearDepthWeight * 0.200000003 + 0.800000012;
  float viewDistanceWeight = saturate(0.5 * (-2.0 + viewDistance));
  viewDistanceWeight = 1.0 + -viewDistanceWeight;

  float3 cameraDelta =
      -cb_xPrevViewToWorld._m03_m13_m23
      + viewToWorld._m03_m13_m23;
  float cameraMotion = sqrt(dot(cameraDelta, cameraDelta));
  float motionScale = max(0.00999999978, surface.viewDepth);
  motionScale = log2(motionScale);
  motionScale = 1.5 * motionScale;
  motionScale = exp2(motionScale);
  motionScale = 0.00499999989 * motionScale;
  motionScale = max(0.00999999978, motionScale);
  float cameraStability = min(1.0, cameraMotion / motionScale);
  cameraStability = 1.0 + -cameraStability;

  float volatility = ReadUpscaleVolatility(
      tVolatile, LinearClampClamp_s, currentUv);
  float reprojectionStability = 1.0 + -abs(volatility);
  bool forceCurrentPixel = volatility < 0.0;
  float lostStability = 1.0 + -reprojectionStability;
  float forcedStability = lostStability
      * (-nearDepthWeight * 0.600000024 + 1.0);
  if (forceCurrentPixel)
  {
    previousUv = currentUv;
    reprojectionStability = forcedStability;
  }
  reprojectionStability =
      cb_fRenderScaleStability * reprojectionStability;
  previousUv = min(cb_vPrevUvLimit.xy, previousUv);
  float2 previous = tTemporalAo.SampleLevel(
      LinearClampClamp_s, previousUv, 0.0).xy;

  float2 historyResponse = saturate(
      float2(0.100000001, 0.5) * surface.viewDepth.xx);
  historyResponse = historyResponse * float2(0.139999986, 0.139999986)
      + float2(0.0699999928, 0.0);
  historyResponse = cb_fFrameRateScale * historyResponse
      + float2(0.75, 0.819999993);
  float motionResponse = cameraStability * 0.600000024 + 0.400000006;
  float stableMotionResponse = forceCurrentPixel ? 1.0 : motionResponse;
  float stabilityFloor = reprojectionStability * 0.875 + 0.125;
  float aoHistoryWeight = historyResponse.x * stableMotionResponse;
  aoHistoryWeight = stabilityFloor * aoHistoryWeight;
  aoHistoryWeight = aoHistoryWeight * nearDepthWeight;

  float aoDifference = -previous.x + current.x;
  bool aoAccepted = abs(aoDifference) < 0.5;
  aoAccepted = current.x >= 0.0500000007 ? aoAccepted : false;
  aoAccepted = current.x < 0.949999988 ? aoAccepted : false;
  aoHistoryWeight = aoAccepted ? aoHistoryWeight : 0.0;
  float auxiliaryHistoryWeight = historyResponse.y * motionResponse;
  auxiliaryHistoryWeight = auxiliaryResponse
      * auxiliaryHistoryWeight * viewDistanceWeight;

  float2 historyWeight = float2(
      aoHistoryWeight, auxiliaryHistoryWeight);
  return historyWeight * (previous + -current) + current;
}
