// Family-bound wrappers. This file is included after the recovered constant
// buffers, textures, and samplers, so entry points can use domain values
// without forwarding the complete resource ABI to every primitive.

struct UpscalePosition
{
  float3 view;
  float3 world;
};

struct UpscaleSurface
{
  int2 pixel;
  float viewDepth;
  float3 viewPosition;
  float3 worldPosition;
  float ao;
  float4 sss;
  float sssComplement;
  float sssOcclusion;
};

struct UpscaleCascadeLighting
{
  float shadowResponse;
  float visibility;
};

UpscalePosition ReconstructOrthoUpscalePosition(
    float2 unscaledUv, float viewDepth)
{
  // Preserve the two recovered UV operations instead of folding their MADs.
  float2 clipPosition =
      unscaledUv * float2(1.0, -1.0) + float2(0.0, 1.0);
  clipPosition =
      clipPosition * float2(2.0, 2.0) + float2(-1.0, -1.0);

  UpscalePosition result;
  result.view.z = -viewDepth;
  result.view.xy =
      cb_vNearFarViewCorner.zw * clipPosition + cb_vViewTranslate.xy;
  result.world = TransformUpscalePosition(viewToWorld, result.view);
  return result;
}

UpscaleSurface GatherBoundUpscaleSurface(
    float2 unscaledUv, int2 pixel, float viewDepth)
{
  UpscaledAoSss spatial = FilterAoSssCross(
      tAoDepth, tIndirect_Ao, tSSS, tMaterial, LinearClampClamp_s,
      pixel, viewDepth, cb_vTargetSize.xy,
      cb_vRenderScale.xy, cb_vContainerPixelSize.xy,
      cb_settings.vInvScale.xy, cb_settings.vUvLimit.xy,
      cb_f720To4K, cb_uFrameCount, cb_fFrameRateScale);
  UpscalePosition position =
      ReconstructOrthoUpscalePosition(unscaledUv, viewDepth);
  bool hasGeometry = viewDepth < UPSCALE_DEPTH_RANGE;

  UpscaleSurface result;
  result.pixel = pixel;
  result.viewDepth = viewDepth;
  result.viewPosition = position.view;
  result.worldPosition = position.world;
  result.ao = spatial.ao;
  result.sss = spatial.sss;
  result.sssComplement = hasGeometry ? 1.0 + -spatial.sss.x : 0.0;
  result.sssOcclusion = hasGeometry ? spatial.sss.x : 1.0;
  return result;
}

UpscaleSurface GatherBoundPerspectiveUpscaleSurface(
    float2 unscaledUv, int2 pixel, float viewDepth)
{
  UpscaledAoSss spatial = FilterAoSssCross(
      tAoDepth, tIndirect_Ao, tSSS, tMaterial, LinearClampClamp_s,
      pixel, viewDepth, cb_vTargetSize.xy,
      cb_vRenderScale.xy, cb_vContainerPixelSize.xy,
      cb_settings.vInvScale.xy, cb_settings.vUvLimit.xy,
      cb_f720To4K, cb_uFrameCount, cb_fFrameRateScale);

  float2 clipPosition =
      unscaledUv * float2(1.0, -1.0) + float2(0.0, 1.0);
  clipPosition =
      clipPosition * float2(2.0, 2.0) + float2(-1.0, -1.0);
  float3 viewPosition;
  viewPosition.xy = cb_vNearFarViewCorner.zw * clipPosition;
  viewPosition.xy = viewPosition.xy * viewDepth.xx;
  viewPosition.z = -viewDepth;

  bool hasGeometry = viewDepth < UPSCALE_DEPTH_RANGE;
  UpscaleSurface result;
  result.pixel = pixel;
  result.viewDepth = viewDepth;
  result.viewPosition = viewPosition;
  result.worldPosition =
      TransformUpscalePosition(viewToWorld, viewPosition);
  result.ao = spatial.ao;
  result.sss = spatial.sss;
  result.sssComplement = hasGeometry ? 1.0 + -spatial.sss.x : 0.0;
  result.sssOcclusion = hasGeometry ? spatial.sss.x : 1.0;
  return result;
}

UpscaleCascadeLighting EvaluateBoundUpscaleCascadeLighting(
    UpscaleSurface surface)
{
  UpscaleCascadeLighting result;
  if (!(0.00999999978 < surface.sssOcclusion))
  {
    result.shadowResponse = 0.0;
    result.visibility = 1.0;
    return result;
  }

  float3 normal = DecodeUpscaleNormal(
      tNormal.Load(int3(surface.pixel, 0)).xy);
  float cameraRangeFade =
      -surface.viewDepth * cb_vInverseCameraRange.x + 1.0;
  UpscaleCascadeSelection activeCascade = SelectUpscaleCascade(
      surface.worldPosition,
      cb_arrCascades[0], cb_arrCascades[1],
      cb_arrCascades[2], cb_arrCascades[3]);
  float shadow = EvaluateUpscaleMediumCascadeShadow(
      taCascades, sShadowSamplerLinear_s, activeCascade,
      surface.worldPosition, cameraRangeFade,
      cb_vCascadeSplits, cb_vCascadeSize, cb_vCascadePixelSize,
      cb_arrCascades[1], cb_arrCascades[2], cb_arrCascades[3]);
  shadow = ApplyUpscaleDirectionalFacing(
      shadow, normal, cb_vDirectionalLightDirectionView.xyz);
  result.shadowResponse = shadow;
  result.visibility = shadow;
  return result;
}

UpscaleCascadeLighting EvaluateBoundLowUpscaleCascadeLighting(
    UpscaleSurface surface)
{
  UpscaleCascadeLighting result;
  if (!(0.00999999978 < surface.sssOcclusion))
  {
    result.shadowResponse = 0.0;
    result.visibility = 1.0;
    return result;
  }

  float3 normal = DecodeUpscaleNormal(
      tNormal.Load(int3(surface.pixel, 0)).xy);
  float cameraRangeFade =
      -surface.viewDepth * cb_vInverseCameraRange.x + 1.0;
  UpscaleCascadeSelection activeCascade = SelectUpscaleCascade(
      surface.worldPosition,
      cb_arrCascades[0], cb_arrCascades[1],
      cb_arrCascades[2], cb_arrCascades[3]);
  float shadow = EvaluateUpscaleLowCascadeShadow(
      taCascades, sShadowSamplerLinear_s, activeCascade,
      surface.worldPosition, cameraRangeFade,
      cb_vCascadeSplits, cb_vCascadeSize, cb_vCascadePixelSize,
      cb_arrCascades[1], cb_arrCascades[2], cb_arrCascades[3]);
  shadow = ApplyUpscaleDirectionalFacing(
      shadow, normal, cb_vDirectionalLightDirectionView.xyz);
  result.shadowResponse = shadow;
  result.visibility = shadow;
  return result;
}

UpscaleTemporalResult ResolveBoundUpscaleTemporal(
    UpscaleSurface surface,
    UpscaleCascadeLighting cascade,
    float2 currentUv)
{
  return ResolveUpscaleTemporal(
      tTemporalAo, tTemporalSSS, tVolatile, LinearClampClamp_s,
      currentUv, surface.viewDepth, surface.viewPosition,
      surface.worldPosition, surface.ao, surface.sss,
      surface.sssComplement, surface.sssOcclusion,
      cascade.shadowResponse, cb_xPrevWorldToViewProjection,
      cb_xPrevViewToWorld._m03_m13_m23, viewToWorld._m03_m13_m23,
      cb_vPrevRenderScale, cb_vPrevUvLimit, cb_fRenderScaleStability,
      cb_fFrameRateScale, cb_settings.vuSSSwaps);
}

UpscaleTemporalResult ResolveBoundUpscaleTemporalWithoutCascadeHistory(
    UpscaleSurface surface,
    UpscaleCascadeLighting cascade,
    float2 currentUv)
{
  return ResolveUpscaleTemporalWithoutCascadeHistory(
      tTemporalAo, tTemporalSSS, tVolatile, LinearClampClamp_s,
      currentUv, surface.viewDepth, surface.viewPosition,
      surface.worldPosition, surface.ao, surface.sss,
      surface.sssComplement, surface.sssOcclusion,
      cascade.shadowResponse, cb_xPrevWorldToViewProjection,
      cb_xPrevViewToWorld._m03_m13_m23, viewToWorld._m03_m13_m23,
      cb_vPrevRenderScale, cb_vPrevUvLimit, cb_fRenderScaleStability,
      cb_fFrameRateScale, cb_settings.vuSSSwaps);
}
