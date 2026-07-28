// Bound helpers for AO plus temporally accumulated depth-derived cascades.

struct UpscaledAo
{
  float value;
};

struct AoAccumulator
{
  float coherentValue;
  float coherentWeight;
  float sparseValue;
  float sparseWeight;
};

struct BoundAoPosition
{
  float3 viewPosition;
  float3 worldPosition;
};

void AccumulateAoFootprint(
    int2 samplePixel,
    float coherentBias,
    float centerDepth,
    float threshold,
    float inverseThreshold,
    float responseExponent,
    float edgeResponse,
    inout AoAccumulator accumulator)
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
  float ao = tIndirect_Ao.SampleLevel(
      LinearClampClamp_s, sourceUv, 0.0).w;
  float coverage = ComputeUpscaleCoverageWeight(
      depthError, threshold, responseExponent);

  if (acceptedCount <= 3.0)
  {
    float weight = acceptedCount * 0.25 + 0.00999999978;
    accumulator.sparseValue = ao * weight + accumulator.sparseValue;
    accumulator.sparseWeight = weight + accumulator.sparseWeight;
  }
  else
  {
    float weight = adjustedGaussian * coverage;
    accumulator.coherentValue = ao * weight + accumulator.coherentValue;
    accumulator.coherentWeight =
        adjustedGaussian * coverage + accumulator.coherentWeight;
  }
}

UpscaledAo FilterBoundAoCross(int2 pixel, float centerDepth)
{
  UpscaledAo result;
  if (!(centerDepth < UPSCALE_DEPTH_RANGE))
  {
    result.value = 1.0;
    return result;
  }

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

  AoAccumulator accumulated;
  accumulated.coherentValue = 0.0;
  accumulated.coherentWeight = 0.0;
  accumulated.sparseValue = 0.0;
  accumulated.sparseWeight = 0.0;
  AccumulateAoFootprint(pixel + int2(0, -int(radius)), 0.125,
      centerDepth, threshold, inverseThreshold, thresholdParameters.y,
      material.edgeResponse, accumulated);
  AccumulateAoFootprint(pixel + int2(-int(radius), 0), 0.125,
      centerDepth, threshold, inverseThreshold, thresholdParameters.y,
      material.edgeResponse, accumulated);
  AccumulateAoFootprint(pixel, 0.5,
      centerDepth, threshold, inverseThreshold, thresholdParameters.y,
      material.edgeResponse, accumulated);
  AccumulateAoFootprint(pixel + int2(int(radius), 0), 0.125,
      centerDepth, threshold, inverseThreshold, thresholdParameters.y,
      material.edgeResponse, accumulated);
  AccumulateAoFootprint(pixel + int2(0, int(radius)), 0.125,
      centerDepth, threshold, inverseThreshold, thresholdParameters.y,
      material.edgeResponse, accumulated);

  float sparseValue = material.edgeResponse * 0.0399999991
      < accumulated.sparseWeight
      ? accumulated.sparseValue / accumulated.sparseWeight : 1.0;
  result.value = 0.0 < accumulated.coherentWeight
      ? accumulated.coherentValue / accumulated.coherentWeight : sparseValue;
  return result;
}

BoundAoPosition ReconstructBoundPerspectiveAoPosition(
    float2 unscaledUv, float viewDepth)
{
  float2 clipPosition =
      unscaledUv * float2(1.0, -1.0) + float2(0.0, 1.0);
  clipPosition =
      clipPosition * float2(2.0, 2.0) + float2(-1.0, -1.0);
  float2 viewXY = cb_vNearFarViewCorner.zw * clipPosition;
  viewXY = viewXY * viewDepth.xx;
  BoundAoPosition result;
  result.viewPosition = float3(viewXY, -viewDepth);
  result.worldPosition = TransformUpscalePosition(
      viewToWorld, result.viewPosition);
  return result;
}

BoundAoPosition ReconstructBoundOrthoAoPosition(
    float2 unscaledUv, float viewDepth)
{
  float2 clipPosition =
      unscaledUv * float2(1.0, -1.0) + float2(0.0, 1.0);
  clipPosition =
      clipPosition * float2(2.0, 2.0) + float2(-1.0, -1.0);
  float2 viewXY =
      cb_vNearFarViewCorner.zw * clipPosition + cb_vViewTranslate.xy;
  BoundAoPosition result;
  result.viewPosition = float3(viewXY, -viewDepth);
  result.worldPosition = TransformUpscalePosition(
      viewToWorld, result.viewPosition);
  return result;
}

float EvaluateBoundAoDepthCascade(
    int2 pixel,
    BoundAoPosition sceneSurface,
    float sceneDepth,
    bool mediumQuality)
{
  float3 normal = DecodeUpscaleNormal(
      tNormal.Load(int3(pixel, 0)).xy);
  float lightFacing = dot(
      normal, cb_vDirectionalLightDirectionView.xyz);
  if (!(lightFacing < 0.330000013))
    return 0.0;

  float cameraRangeFade =
      -sceneDepth * cb_vInverseCameraRange.x + 1.0;
  UpscaleCascadeSelection activeCascade = SelectUpscaleCascade(
      sceneSurface.worldPosition,
      cb_arrCascades[0], cb_arrCascades[1],
      cb_arrCascades[2], cb_arrCascades[3]);
  float visibility;
  if (mediumQuality)
  {
    visibility = EvaluateUpscaleMediumCascadeShadow(
        taCascades, sShadowSamplerLinear_s, activeCascade,
        sceneSurface.worldPosition, cameraRangeFade,
        cb_vCascadeSplits, cb_vCascadeSize, cb_vCascadePixelSize,
        cb_arrCascades[1], cb_arrCascades[2], cb_arrCascades[3]);
  }
  else
  {
    visibility = EvaluateUpscaleLowCascadeShadow(
        taCascades, sShadowSamplerLinear_s, activeCascade,
        sceneSurface.worldPosition, cameraRangeFade,
        cb_vCascadeSplits, cb_vCascadeSize, cb_vCascadePixelSize,
        cb_arrCascades[1], cb_arrCascades[2], cb_arrCascades[3]);
  }
  return ApplyUpscaleDirectionalFacing(
      visibility, normal, cb_vDirectionalLightDirectionView.xyz);
}

float2 ResolveBoundAoCascadeTemporal(
    float2 currentUv,
    float viewDepth,
    BoundAoPosition hzbSurface,
    float2 current,
    float acceptedCascadeResponse,
    float rejectedCascadeResponse)
{
  float3 previousClip = ProjectUpscalePosition(
      cb_xPrevWorldToViewProjection, hzbSurface.worldPosition);
  float2 insidePrevious = abs(previousClip.xy) < previousClip.zz;
  if (!(insidePrevious.x && insidePrevious.y))
    return current;

  float viewDistance = dot(
      hzbSurface.viewPosition, hzbSurface.viewPosition);
  viewDistance = sqrt(viewDistance);
  float2 previousUv = previousClip.xy / previousClip.zz;
  previousUv = previousUv * float2(0.5, -0.5)
      + float2(0.5, 0.5);
  previousUv = cb_vPrevRenderScale.xy * previousUv;
  float nearDepthWeight = saturate(
      4.0 * (-0.800000012 + viewDepth));
  nearDepthWeight = nearDepthWeight * 0.200000003 + 0.800000012;
  float viewDistanceWeight = saturate(0.5 * (-2.0 + viewDistance));
  viewDistanceWeight = 1.0 + -viewDistanceWeight;

  float3 cameraDelta =
      -cb_xPrevViewToWorld._m03_m13_m23
      + viewToWorld._m03_m13_m23;
  float cameraMotion = sqrt(dot(cameraDelta, cameraDelta));
  float motionScale = max(0.00999999978, viewDepth);
  motionScale = log2(motionScale);
  motionScale = 1.5 * motionScale;
  motionScale = exp2(motionScale);
  motionScale = 0.00499999989 * motionScale;
  motionScale = max(0.00999999978, motionScale);
  float cameraStability = cameraMotion / motionScale;
  cameraStability = min(1.0, cameraStability);
  cameraStability = 1.0 + -cameraStability;

  float volatility = ReadUpscaleVolatility(
      tVolatile, LinearClampClamp_s, currentUv);
  float reprojectionStability = 1.0 + -abs(volatility);
  bool forcedCurrentPixel = volatility < 0.0;
  float lostStability = 1.0 + -reprojectionStability;
  float forcedStability = lostStability
      * (-nearDepthWeight * 0.600000024 + 1.0);
  if (forcedCurrentPixel)
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
      float2(0.100000001, 0.5) * viewDepth.xx);
  historyResponse = historyResponse * float2(0.139999986, 0.139999986)
      + float2(0.0699999928, 0.0);
  historyResponse = cb_fFrameRateScale * historyResponse
      + float2(0.75, 0.819999993);
  float motionResponse = cameraStability * 0.600000024 + 0.400000006;
  float stableMotion = forcedCurrentPixel ? 1.0 : motionResponse;
  float aoHistoryWeight = historyResponse.x * stableMotion;
  float stabilityFloor = reprojectionStability * 0.875 + 0.125;
  aoHistoryWeight = stabilityFloor * aoHistoryWeight;
  aoHistoryWeight = aoHistoryWeight * nearDepthWeight;

  float2 difference = current + -previous;
  bool2 accepted = abs(difference) < float2(0.5, 0.75);
  accepted = current >= float2(0.0500000007, 0.25)
      ? accepted : false;
  accepted = current < float2(0.949999988, 0.75)
      ? accepted : false;
  float aoWeight = accepted.x ? aoHistoryWeight : 0.0;
  float cascadeCoefficient = accepted.y
      ? acceptedCascadeResponse : rejectedCascadeResponse;
  float cascadeWeight =
      viewDistanceWeight * cascadeCoefficient + (accepted.y ? 1.0 : 0.0);
  cascadeWeight = historyResponse.y * stableMotion * cascadeWeight;
  float2 historyWeight = float2(aoWeight, cascadeWeight);
  float2 historyDelta = previous + -current;
  return historyWeight * historyDelta + current;
}
