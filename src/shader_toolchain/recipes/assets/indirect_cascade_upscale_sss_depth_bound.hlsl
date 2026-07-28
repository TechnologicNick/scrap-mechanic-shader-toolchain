// Bound helpers for SSS permutations whose cascade is evaluated at tDepth.

struct UpscaledSss
{
  float4 value;
};

struct SssAccumulator
{
  float4 coherentValue;
  float coherentWeight;
  float4 sparseValue;
  float sparseWeight;
};

struct BoundSssPosition
{
  float3 viewPosition;
  float3 worldPosition;
};

void AccumulateSssFootprint(
    int2 samplePixel,
    float coherentBias,
    float centerDepth,
    float threshold,
    float inverseThreshold,
    float responseExponent,
    float edgeResponse,
    inout SssAccumulator accumulator)
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
  float4 sss = tSSS.SampleLevel(
      LinearClampClamp_s, sourceUv, 0.0);
  float coverage = ComputeUpscaleCoverageWeight(
      depthError, threshold, responseExponent);

  if (acceptedCount <= 3.0)
  {
    float weight = acceptedCount * 0.25 + 0.00999999978;
    accumulator.sparseValue = sss * weight + accumulator.sparseValue;
    accumulator.sparseWeight = weight + accumulator.sparseWeight;
  }
  else
  {
    float weight = coverage * adjustedGaussian;
    accumulator.coherentValue =
        weight * sss + accumulator.coherentValue;
    accumulator.coherentWeight =
        adjustedGaussian * coverage + accumulator.coherentWeight;
  }
}

UpscaledSss FilterBoundSssCross(int2 pixel, float centerDepth)
{
  UpscaledSss result;
  if (!(centerDepth < UPSCALE_DEPTH_RANGE))
  {
    result.value = 0.0;
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

  SssAccumulator accumulated;
  accumulated.coherentValue = 0.0;
  accumulated.coherentWeight = 0.0;
  accumulated.sparseValue = 0.0;
  accumulated.sparseWeight = 0.0;

  AccumulateSssFootprint(pixel + int2(0, -int(radius)), 0.125,
      centerDepth, threshold, inverseThreshold, thresholdParameters.y,
      material.edgeResponse, accumulated);
  AccumulateSssFootprint(pixel + int2(-int(radius), 0), 0.125,
      centerDepth, threshold, inverseThreshold, thresholdParameters.y,
      material.edgeResponse, accumulated);
  AccumulateSssFootprint(pixel, 0.5,
      centerDepth, threshold, inverseThreshold, thresholdParameters.y,
      material.edgeResponse, accumulated);
  AccumulateSssFootprint(pixel + int2(int(radius), 0), 0.125,
      centerDepth, threshold, inverseThreshold, thresholdParameters.y,
      material.edgeResponse, accumulated);
  AccumulateSssFootprint(pixel + int2(0, int(radius)), 0.125,
      centerDepth, threshold, inverseThreshold, thresholdParameters.y,
      material.edgeResponse, accumulated);

  float4 sparseValue = 0.0 < accumulated.sparseWeight
      ? accumulated.sparseValue / accumulated.sparseWeight : 0.0;
  result.value = 0.0 < accumulated.coherentWeight
      ? accumulated.coherentValue / accumulated.coherentWeight : sparseValue;
  return result;
}

BoundSssPosition ReconstructBoundPerspectiveSssPosition(
    float2 unscaledUv, float viewDepth)
{
  float2 clipPosition =
      unscaledUv * float2(1.0, -1.0) + float2(0.0, 1.0);
  clipPosition =
      clipPosition * float2(2.0, 2.0) + float2(-1.0, -1.0);
  float2 viewXY = cb_vNearFarViewCorner.zw * clipPosition;
  viewXY = viewXY * viewDepth.xx;
  BoundSssPosition result;
  result.viewPosition = float3(viewXY, -viewDepth);
  result.worldPosition = TransformUpscalePosition(
      viewToWorld, result.viewPosition);
  return result;
}

BoundSssPosition ReconstructBoundOrthoSssPosition(
    float2 unscaledUv, float viewDepth)
{
  float2 clipPosition =
      unscaledUv * float2(1.0, -1.0) + float2(0.0, 1.0);
  clipPosition =
      clipPosition * float2(2.0, 2.0) + float2(-1.0, -1.0);
  float2 viewXY =
      cb_vNearFarViewCorner.zw * clipPosition + cb_vViewTranslate.xy;
  BoundSssPosition result;
  result.viewPosition = float3(viewXY, -viewDepth);
  result.worldPosition = TransformUpscalePosition(
      viewToWorld, result.viewPosition);
  return result;
}

float EvaluateBoundDepthCascadeImpl(
    int2 pixel,
    float hzbDepth,
    float sceneDepth,
    float sssAmount,
    BoundSssPosition sceneSurface,
    bool mediumQuality)
{
  bool validSceneDepth = sceneDepth < UPSCALE_DEPTH_RANGE;
  validSceneDepth = sceneDepth >= hzbDepth ? validSceneDepth : false;
  if (!(validSceneDepth && 0.00999999978 < sssAmount))
    return 1.0;

  float3 normal = DecodeUpscaleNormal(
      tNormal.Load(int3(pixel, 0)).xy);
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

float4 ResolveBoundSssTemporal(
    float2 currentUv,
    float viewDepth,
    BoundSssPosition hzbSurface,
    float4 currentSss)
{
  float3 previousClip = ProjectUpscalePosition(
      cb_xPrevWorldToViewProjection, hzbSurface.worldPosition);
  float2 insidePrevious = abs(previousClip.xy) < previousClip.zz;
  if (!(insidePrevious.x && insidePrevious.y))
    return currentSss;

  float viewDistance = dot(
      hzbSurface.viewPosition, hzbSurface.viewPosition);
  viewDistance = sqrt(viewDistance);
  float2 previousUv = previousClip.xy / previousClip.zz;
  previousUv = previousUv * float2(0.5, -0.5)
      + float2(0.5, 0.5);
  previousUv = cb_vPrevRenderScale.xy * previousUv;

  float nearDepthWeight = -0.800000012 + viewDepth;
  nearDepthWeight = saturate(4.0 * nearDepthWeight);
  nearDepthWeight = nearDepthWeight * 0.200000003 + 0.800000012;
  float viewDistanceWeight = -2.0 + viewDistance;
  viewDistanceWeight = saturate(0.5 * viewDistanceWeight);
  viewDistanceWeight = 1.0 + -viewDistanceWeight;

  float3 cameraDelta =
      -cb_xPrevViewToWorld._m03_m13_m23
      + viewToWorld._m03_m13_m23;
  float cameraMotion = dot(cameraDelta, cameraDelta);
  cameraMotion = sqrt(cameraMotion);
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
  float4 previousSss = SwizzleUpscaleSss(
      tTemporalSSS.SampleLevel(
          LinearClampClamp_s, previousUv, 0.0),
      cb_settings.vuSSSwaps);

  float sssComplement = 1.0 + -currentSss.x;
  float surfaceWeight = 9.99999975e-05 < sssComplement
      ? 0.959999979 : 0.5;
  float stableMotion = forcedCurrentPixel ? 1.0 : cameraStability;
  stableMotion = stableMotion * 0.600000024 + 0.400000006;
  float historyWeight = surfaceWeight * stableMotion;
  float stabilityFloor = reprojectionStability * 0.875 + 0.125;
  historyWeight = stabilityFloor * historyWeight;
  float spatialStability = min(nearDepthWeight, viewDistanceWeight);
  historyWeight = historyWeight * spatialStability;
  float4 historyDelta = previousSss + -currentSss;
  return historyWeight * historyDelta + currentSss;
}
