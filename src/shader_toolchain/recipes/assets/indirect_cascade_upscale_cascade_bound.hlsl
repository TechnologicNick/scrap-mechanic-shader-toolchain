// Bound helpers for cascade-only permutations. Included after their recovered
// resources; deliberately independent of AO, indirect, SSS, and CB_SETTINGS.

struct UpscaleCascadeSurface
{
  int2 pixel;
  float viewDepth;
  float3 viewPosition;
  float3 worldPosition;
  float3 normal;
};

UpscaleCascadeSurface GatherBoundPerspectiveCascadeSurface(
    float2 unscaledUv, int2 pixel, float viewDepth)
{
  float2 clipPosition =
      unscaledUv * float2(1.0, -1.0) + float2(0.0, 1.0);
  clipPosition =
      clipPosition * float2(2.0, 2.0) + float2(-1.0, -1.0);

  float3 viewPosition;
  viewPosition.xy = cb_vNearFarViewCorner.zw * clipPosition;
  viewPosition.xy = viewPosition.xy * viewDepth.xx;
  viewPosition.z = -viewDepth;

  UpscaleCascadeSurface result;
  result.pixel = pixel;
  result.viewDepth = viewDepth;
  result.viewPosition = viewPosition;
  result.worldPosition =
      TransformUpscalePosition(viewToWorld, viewPosition);
  result.normal = DecodeUpscaleNormal(
      tNormal.Load(int3(pixel, 0)).xy);
  return result;
}

bool HasNegativeUpscaleVolatility(
    Texture2D<float> volatilityTexture,
    SamplerState linearSampler,
    float2 uv)
{
  float4 negative = volatilityTexture.Gather(linearSampler, uv) < 0.0;
  int2 pairs = (int2)negative.zw | (int2)negative.xy;
  int neighborhoodNegative = pairs.y | pairs.x;
  float center = volatilityTexture.SampleLevel(linearSampler, uv, 0.0);
  int centerNegative = center < 0.0 ? 1 : 0;
  return bool(neighborhoodNegative | centerNegative);
}

float EvaluateBoundLowCascadeOnlyLighting(
    UpscaleCascadeSurface surface)
{
  float lightFacing = dot(
      surface.normal, cb_vDirectionalLightDirectionView.xyz);
  if (!(lightFacing < 0.330000013))
    return 0.0;

  float cameraRangeFade =
      -surface.viewDepth * cb_vInverseCameraRange.x + 1.0;
  UpscaleCascadeSelection activeCascade = SelectUpscaleCascade(
      surface.worldPosition,
      cb_arrCascades[0], cb_arrCascades[1],
      cb_arrCascades[2], cb_arrCascades[3]);
  float visibility = EvaluateUpscaleLowCascadeShadow(
      taCascades, sShadowSamplerLinear_s, activeCascade,
      surface.worldPosition, cameraRangeFade,
      cb_vCascadeSplits, cb_vCascadeSize, cb_vCascadePixelSize,
      cb_arrCascades[1], cb_arrCascades[2], cb_arrCascades[3]);
  return ApplyUpscaleDirectionalFacing(
      visibility, surface.normal,
      cb_vDirectionalLightDirectionView.xyz);
}

float EvaluateBoundMediumCascadeOnlyLighting(
    UpscaleCascadeSurface surface)
{
  float lightFacing = dot(
      surface.normal, cb_vDirectionalLightDirectionView.xyz);
  if (!(lightFacing < 0.330000013))
    return 0.0;

  float cameraRangeFade =
      -surface.viewDepth * cb_vInverseCameraRange.x + 1.0;
  UpscaleCascadeSelection activeCascade = SelectUpscaleCascade(
      surface.worldPosition,
      cb_arrCascades[0], cb_arrCascades[1],
      cb_arrCascades[2], cb_arrCascades[3]);
  float visibility = EvaluateUpscaleMediumCascadeShadow(
      taCascades, sShadowSamplerLinear_s, activeCascade,
      surface.worldPosition, cameraRangeFade,
      cb_vCascadeSplits, cb_vCascadeSize, cb_vCascadePixelSize,
      cb_arrCascades[1], cb_arrCascades[2], cb_arrCascades[3]);
  return ApplyUpscaleDirectionalFacing(
      visibility, surface.normal,
      cb_vDirectionalLightDirectionView.xyz);
}

float ResolveBoundCascadeOnlyTemporalImpl(
    float2 currentUv,
    UpscaleCascadeSurface surface,
    float currentVisibility,
    float acceptedResponse,
    float rejectedResponse)
{
  float3 previousClip = ProjectUpscalePosition(
      cb_xPrevWorldToViewProjection, surface.worldPosition);
  float2 insidePrevious = abs(previousClip.xy) < previousClip.zz;
  if (!(insidePrevious.x && insidePrevious.y))
    return currentVisibility;

  float viewDistance = dot(
      surface.viewPosition, surface.viewPosition);
  viewDistance = sqrt(viewDistance);
  float viewDistanceWeight = -2.0 + viewDistance;
  viewDistanceWeight = saturate(0.5 * viewDistanceWeight);
  viewDistanceWeight = 1.0 + -viewDistanceWeight;

  float2 previousUv = previousClip.xy / previousClip.zz;
  previousUv = previousUv * float2(0.5, -0.5)
      + float2(0.5, 0.5);
  previousUv = cb_vPrevRenderScale.xy * previousUv;

  float3 cameraDelta =
      -cb_xPrevViewToWorld._m03_m13_m23
      + viewToWorld._m03_m13_m23;
  float cameraMotion = dot(cameraDelta, cameraDelta);
  cameraMotion = sqrt(cameraMotion);
  float motionScale = max(0.00999999978, surface.viewDepth);
  motionScale = log2(motionScale);
  motionScale = 1.5 * motionScale;
  motionScale = exp2(motionScale);
  motionScale = 0.00499999989 * motionScale;
  motionScale = max(0.00999999978, motionScale);
  float cameraStability = cameraMotion / motionScale;
  cameraStability = min(1.0, cameraStability);
  cameraStability = 1.0 + -cameraStability;

  bool forceCurrentPixel = HasNegativeUpscaleVolatility(
      tVolatile, LinearClampClamp_s, currentUv);
  previousUv = forceCurrentPixel ? currentUv : previousUv;
  previousUv = min(cb_vPrevUvLimit.xy, previousUv);
  float previousVisibility = tTemporalAo.SampleLevel(
      LinearClampClamp_s, previousUv, 0.0).y;

  float historyResponse = saturate(0.5 * surface.viewDepth);
  historyResponse = cb_fFrameRateScale * historyResponse;
  historyResponse = historyResponse * 0.139999986 + 0.819999993;
  cameraStability = cameraStability * 0.600000024 + 0.400000006;
  historyResponse = historyResponse * cameraStability;

  float historyDifference =
      -previousVisibility + currentVisibility;
  bool historyAccepted = abs(historyDifference) < 0.75;
  historyAccepted = currentVisibility >= 0.25
      ? historyAccepted : false;
  historyAccepted = currentVisibility < 0.75
      ? historyAccepted : false;
  float acceptanceResponse = historyAccepted
      ? acceptedResponse : rejectedResponse;
  float acceptedValue = historyAccepted ? 1.0 : 0.0;
  float historyWeight =
      viewDistanceWeight * acceptanceResponse + acceptedValue;
  historyWeight = historyResponse * historyWeight;
  float previousDelta =
      previousVisibility + -currentVisibility;
  return historyWeight * previousDelta + currentVisibility;
}

float ResolveBoundLowMediumCascadeOnlyTemporal(
    float2 currentUv,
    UpscaleCascadeSurface surface,
    float currentVisibility)
{
  return ResolveBoundCascadeOnlyTemporalImpl(
      currentUv, surface, currentVisibility,
      -0.180000007, 0.819999993);
}

float ResolveBoundHighCascadeOnlyTemporal(
    float2 currentUv,
    UpscaleCascadeSurface surface,
    float currentVisibility)
{
  return ResolveBoundCascadeOnlyTemporalImpl(
      currentUv, surface, currentVisibility,
      -0.350000024, 0.649999976);
}
