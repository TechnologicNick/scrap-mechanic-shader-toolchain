// Bound helpers for indirect-only permutations. Included after their recovered
// resources and settings ABI.

struct UpscaledIndirect
{
  float3 lighting;
  float edgeResponse;
};

struct IndirectAccumulator
{
  float3 coherentLighting;
  float coherentWeight;
  float3 sparseLighting;
  float sparseWeight;
};

void AccumulateIndirectFootprint(
    int2 samplePixel,
    float coherentBias,
    float centerDepth,
    float threshold,
    float inverseThreshold,
    float responseExponent,
    float edgeResponse,
    inout IndirectAccumulator accumulator)
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
  float3 indirect = tIndirect_Ao.SampleLevel(
      LinearClampClamp_s, sourceUv, 0.0).xyz;
  float coverage = ComputeUpscaleCoverageWeight(
      depthError, threshold, responseExponent);

  if (acceptedCount <= 3.0)
  {
    float weight = acceptedCount * 0.25 + 0.00999999978;
    accumulator.sparseLighting =
        indirect * weight + accumulator.sparseLighting;
    accumulator.sparseWeight = weight + accumulator.sparseWeight;
  }
  else
  {
    float weight = coverage * adjustedGaussian;
    accumulator.coherentLighting =
        weight * indirect + accumulator.coherentLighting;
    accumulator.coherentWeight =
        adjustedGaussian * coverage + accumulator.coherentWeight;
  }
}

UpscaledIndirect FilterBoundIndirectCross(
    int2 pixel,
    float centerDepth)
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
  float responseExponent = thresholdParameters.y;

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

  IndirectAccumulator accumulated;
  accumulated.coherentLighting = 0.0;
  accumulated.coherentWeight = 0.0;
  accumulated.sparseLighting = 0.0;
  accumulated.sparseWeight = 0.0;

  AccumulateIndirectFootprint(
      pixel + int2(0, -int(radius)), 0.125,
      centerDepth, threshold, inverseThreshold, responseExponent,
      material.edgeResponse, accumulated);
  AccumulateIndirectFootprint(
      pixel + int2(-int(radius), 0), 0.125,
      centerDepth, threshold, inverseThreshold, responseExponent,
      material.edgeResponse, accumulated);
  AccumulateIndirectFootprint(
      pixel, 0.5,
      centerDepth, threshold, inverseThreshold, responseExponent,
      material.edgeResponse, accumulated);
  AccumulateIndirectFootprint(
      pixel + int2(int(radius), 0), 0.125,
      centerDepth, threshold, inverseThreshold, responseExponent,
      material.edgeResponse, accumulated);
  AccumulateIndirectFootprint(
      pixel + int2(0, int(radius)), 0.125,
      centerDepth, threshold, inverseThreshold, responseExponent,
      material.edgeResponse, accumulated);

  float fallback = 0.125 * material.backgroundResponse;
  float3 sparseLighting = material.edgeResponse * 0.0399999991
      < accumulated.sparseWeight
      ? accumulated.sparseLighting / accumulated.sparseWeight
      : fallback.xxx;

  UpscaledIndirect result;
  result.lighting = 0.0 < accumulated.coherentWeight
      ? accumulated.coherentLighting / accumulated.coherentWeight
      : sparseLighting;
  result.edgeResponse = material.edgeResponse;
  return result;
}

float3 ReconstructBoundPerspectiveIndirectPosition(
    float2 unscaledUv, float viewDepth)
{
  float2 clipPosition =
      unscaledUv * float2(1.0, -1.0) + float2(0.0, 1.0);
  clipPosition =
      clipPosition * float2(2.0, 2.0) + float2(-1.0, -1.0);
  float2 viewPosition = cb_vNearFarViewCorner.zw * clipPosition;
  viewPosition = viewPosition * viewDepth.xx;
  return TransformUpscalePosition(
      viewToWorld, float3(viewPosition, -viewDepth));
}

float3 ReconstructBoundOrthoIndirectPosition(
    float2 unscaledUv, float viewDepth)
{
  float2 clipPosition =
      unscaledUv * float2(1.0, -1.0) + float2(0.0, 1.0);
  clipPosition =
      clipPosition * float2(2.0, 2.0) + float2(-1.0, -1.0);
  float2 viewPosition =
      cb_vNearFarViewCorner.zw * clipPosition + cb_vViewTranslate.xy;
  return TransformUpscalePosition(
      viewToWorld, float3(viewPosition, -viewDepth));
}

float3 ResolveBoundIndirectTemporal(
    float2 currentUv,
    float viewDepth,
    float3 worldPosition,
    UpscaledIndirect current)
{
  float3 previousClip = ProjectUpscalePosition(
      cb_xPrevWorldToViewProjection, worldPosition);
  float2 insidePrevious = abs(previousClip.xy) < previousClip.zz;
  if (!(insidePrevious.x && insidePrevious.y))
    return current.lighting;

  float edgePower = current.edgeResponse * current.edgeResponse;
  edgePower = edgePower * edgePower;
  float2 previousUv = previousClip.xy / previousClip.zz;
  previousUv = previousUv * float2(0.5, -0.5)
      + float2(0.5, 0.5);
  bool validPreviousY = previousUv.y >= 0.0;
  previousUv = cb_vPrevRenderScale.xy * previousUv;

  float viewDistanceResponse = max(0.0, -2.0 + viewDepth);
  float nearDepthResponse = saturate(4.0 * (-0.800000012 + viewDepth));
  nearDepthResponse = nearDepthResponse * 0.200000003 + 0.800000012;

  float volatility = ReadUpscaleVolatility(
      tVolatile, LinearClampClamp_s, currentUv);
  float volatilityStability = 1.0 + -abs(volatility);
  bool forceCurrentPixel = volatility < 0.0;
  float forcedStability = 1.0 + -volatilityStability;
  forcedStability = forcedStability
      * (-nearDepthResponse * 0.600000024 + 1.0);
  float2 historyUv = forceCurrentPixel ? currentUv : previousUv;
  float renderStability = forceCurrentPixel
      ? forcedStability : volatilityStability;
  renderStability = cb_fRenderScaleStability * renderStability;
  historyUv = min(cb_vPrevUvLimit.xy, historyUv);
  float3 previousLighting = tTemporalIndirect.SampleLevel(
      LinearClampClamp_s, historyUv, 0.0).xyz;

  float currentLuminance = dot(current.lighting, float3(1.0, 1.0, 1.0));
  float previousLuminance = dot(previousLighting, float3(1.0, 1.0, 1.0));
  float luminanceDifference = previousLuminance + -currentLuminance;
  float rejectionWidth =
      current.edgeResponse * 0.467000008 + 0.333000004;

  float3 cameraDelta =
      -cb_xPrevViewToWorld._m03_m13_m23
      + viewToWorld._m03_m13_m23;
  float cameraMotion = dot(cameraDelta, cameraDelta);
  cameraMotion = sqrt(cameraMotion);
  float motionScale = max(0.00999999978, 0.25 * viewDepth);
  float cameraStability = cameraMotion / motionScale;
  cameraStability = min(1.0, cameraStability);
  cameraStability = 1.0 + -cameraStability;

  float edgeFrameResponse =
      edgePower * -0.120000005 + 0.819999993;
  float depthFrameResponse = min(1.0, 0.100000001 * viewDepth);
  depthFrameResponse =
      depthFrameResponse * 0.120000005 + 0.819999993;
  float frameResponseDelta = 0.699999988 + -depthFrameResponse;
  float frameResponse = edgePower * frameResponseDelta + depthFrameResponse;
  frameResponse = frameResponse + -edgeFrameResponse;
  frameResponse =
      cb_fFrameRateScale * frameResponse + edgeFrameResponse;

  cameraStability = cameraStability * 0.600000024 + 0.400000006;
  cameraStability = validPreviousY ? cameraStability : 1.0;
  float historyWeight = frameResponse * cameraStability;
  float luminanceConfidence =
      abs(luminanceDifference) / rejectionWidth;
  luminanceConfidence = luminanceConfidence * luminanceConfidence;
  luminanceConfidence = min(1.0, luminanceConfidence);
  luminanceConfidence = 1.0 + -luminanceConfidence;
  historyWeight = (forceCurrentPixel ? 1.0 : 0.0)
      * luminanceConfidence * historyWeight;
  historyWeight = renderStability * historyWeight;
  historyWeight = historyWeight * nearDepthResponse;
  float distanceWeight = viewDistanceResponse * 0.875 + 0.125;
  historyWeight = distanceWeight * historyWeight;

  float3 historyDelta = previousLighting + -current.lighting;
  return historyWeight * historyDelta + current.lighting;
}
