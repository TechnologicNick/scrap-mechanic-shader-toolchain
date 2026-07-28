// Composition layer for AO, indirect, SSS, and a depth-derived cascade.
// Spatial filtering and temporal reprojection use the HZB surface; only the
// cascade position, SSS gate, and AO shadow composition use scene depth.
#include "indirect_cascade_upscale_full_bound.hlsl"
#include "indirect_cascade_upscale_cascade_depth_bound.hlsl"

UpscaleCascadeLighting EvaluateBoundFullDepthCascadeImpl(
    inout UpscaleFullSurface surface,
    float3 sceneWorldPosition,
    float sceneDepth,
    bool mediumQuality)
{
  bool validSceneDepth = sceneDepth < UPSCALE_DEPTH_RANGE;
  validSceneDepth = sceneDepth >= surface.common.viewDepth
      ? validSceneDepth : false;
  surface.common.sssComplement = validSceneDepth
      ? 1.0 + -surface.common.sss.x : 0.0;
  surface.common.sssOcclusion = validSceneDepth
      ? surface.common.sss.x : 1.0;

  UpscaleCascadeLighting result;
  if (!(0.00999999978 < surface.common.sssOcclusion))
  {
    result.shadowResponse = 0.0;
    result.visibility = 1.0;
    return result;
  }

  float3 normal = DecodeUpscaleNormal(
      tNormal.Load(int3(surface.common.pixel, 0)).xy);
  float cameraRangeFade =
      -sceneDepth * cb_vInverseCameraRange.x + 1.0;
  UpscaleCascadeSelection activeCascade = SelectUpscaleCascade(
      sceneWorldPosition,
      cb_arrCascades[0], cb_arrCascades[1],
      cb_arrCascades[2], cb_arrCascades[3]);
  float visibility;
  if (mediumQuality)
  {
    visibility = EvaluateUpscaleMediumCascadeShadow(
        taCascades, sShadowSamplerLinear_s, activeCascade,
        sceneWorldPosition, cameraRangeFade,
        cb_vCascadeSplits, cb_vCascadeSize, cb_vCascadePixelSize,
        cb_arrCascades[1], cb_arrCascades[2], cb_arrCascades[3]);
  }
  else
  {
    visibility = EvaluateUpscaleLowCascadeShadow(
        taCascades, sShadowSamplerLinear_s, activeCascade,
        sceneWorldPosition, cameraRangeFade,
        cb_vCascadeSplits, cb_vCascadeSize, cb_vCascadePixelSize,
        cb_arrCascades[1], cb_arrCascades[2], cb_arrCascades[3]);
  }
  visibility = ApplyUpscaleDirectionalFacing(
      visibility, normal, cb_vDirectionalLightDirectionView.xyz);
  result.shadowResponse = visibility;
  result.visibility = visibility;
  return result;
}

UpscaleCascadeLighting EvaluateBoundLowFullDepthCascade(
    inout UpscaleFullSurface surface,
    float3 sceneWorldPosition,
    float sceneDepth)
{
  return EvaluateBoundFullDepthCascadeImpl(
      surface, sceneWorldPosition, sceneDepth, false);
}

UpscaleCascadeLighting EvaluateBoundMediumFullDepthCascade(
    inout UpscaleFullSurface surface,
    float3 sceneWorldPosition,
    float sceneDepth)
{
  return EvaluateBoundFullDepthCascadeImpl(
      surface, sceneWorldPosition, sceneDepth, true);
}

UpscaleTemporalResult ResolveBoundFullDepthAoSssTemporal(
    UpscaleFullSurface surface,
    UpscaleCascadeLighting cascade,
    float2 currentUv,
    float sceneDepth)
{
  UpscaleTemporalResult result;
  result.ao = ComposeUpscaleAo(
      surface.common.ao, surface.common.sssOcclusion,
      cascade.shadowResponse, sceneDepth);
  result.cascadeVisibility = cascade.visibility;
  result.sss = surface.common.sss;

  float3 previousClip = ProjectUpscalePosition(
      cb_xPrevWorldToViewProjection, surface.common.worldPosition);
  float2 insidePrevious = abs(previousClip.xy) < previousClip.zz;
  if (!(insidePrevious.x && insidePrevious.y))
    return result;

  float viewDistance = sqrt(dot(
      surface.common.viewPosition, surface.common.viewPosition));
  float2 previousUv = previousClip.xy / previousClip.zz;
  previousUv = previousUv * float2(0.5, -0.5)
      + float2(0.5, 0.5);
  previousUv = cb_vPrevRenderScale.xy * previousUv;

  float nearDepthWeight = saturate(
      4.0 * (-0.800000012 + surface.common.viewDepth));
  nearDepthWeight = nearDepthWeight * 0.200000003 + 0.800000012;
  float viewDistanceWeight = saturate(0.5 * (-2.0 + viewDistance));
  viewDistanceWeight = 1.0 + -viewDistanceWeight;

  float3 cameraDelta =
      -cb_xPrevViewToWorld._m03_m13_m23
      + viewToWorld._m03_m13_m23;
  float cameraMotion = sqrt(dot(cameraDelta, cameraDelta));
  float motionScale = max(0.00999999978, surface.common.viewDepth);
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

  float previousAo = tTemporalAo.SampleLevel(
      LinearClampClamp_s, previousUv, 0.0).x;
  float4 previousSss = SwizzleUpscaleSss(
      tTemporalSSS.SampleLevel(LinearClampClamp_s, previousUv, 0.0),
      cb_settings.vuSSSwaps);

  float historyResponse = saturate(
      0.100000001 * surface.common.viewDepth);
  historyResponse = historyResponse * 0.139999986 + 0.0699999928;
  historyResponse = cb_fFrameRateScale * historyResponse + 0.75;
  float motionResponse = cameraStability * 0.600000024 + 0.400000006;
  float stableMotionResponse = forceCurrentPixel ? 1.0 : motionResponse;
  float stabilityFloor = reprojectionStability * 0.875 + 0.125;
  float aoHistoryWeight = historyResponse * stableMotionResponse;
  aoHistoryWeight = stabilityFloor * aoHistoryWeight;
  aoHistoryWeight = aoHistoryWeight * nearDepthWeight;

  float aoDifference = -previousAo + result.ao;
  bool aoAccepted = abs(aoDifference) < 0.5;
  aoAccepted = result.ao >= 0.0500000007 ? aoAccepted : false;
  aoAccepted = result.ao < 0.949999988 ? aoAccepted : false;
  float acceptedAoWeight = aoAccepted ? aoHistoryWeight : 0.0;

  float sssSurfaceWeight = 9.99999975e-05 < surface.common.sssComplement
      ? 0.959999979 : 0.5;
  float sssHistoryWeight = sssSurfaceWeight * stableMotionResponse;
  sssHistoryWeight = sssHistoryWeight * stabilityFloor;
  float sssSpatialStability = min(nearDepthWeight, viewDistanceWeight);
  sssHistoryWeight = sssHistoryWeight * sssSpatialStability;

  float4 sssDelta = previousSss + -surface.common.sss;
  result.sss = sssHistoryWeight * sssDelta + surface.common.sss;
  float previousAoDelta = previousAo + -result.ao;
  result.ao = acceptedAoWeight * previousAoDelta + result.ao;
  return result;
}

UpscaleFullTemporalResult ResolveBoundFullDepthTemporalWithoutCascadeHistory(
    UpscaleFullSurface surface,
    UpscaleCascadeLighting cascade,
    float2 currentUv,
    float sceneDepth)
{
  UpscaleTemporalResult aoSss = ResolveBoundFullDepthAoSssTemporal(
      surface, cascade, currentUv, sceneDepth);
  float3 indirect = ResolveBoundIndirectTemporal(
      currentUv, surface.common.viewDepth,
      surface.common.worldPosition, surface.indirect);

  UpscaleFullTemporalResult result;
  result.ao = aoSss.ao;
  result.indirect = indirect;
  result.sss = aoSss.sss;
  result.cascadeVisibility = cascade.visibility;
  return result;
}
