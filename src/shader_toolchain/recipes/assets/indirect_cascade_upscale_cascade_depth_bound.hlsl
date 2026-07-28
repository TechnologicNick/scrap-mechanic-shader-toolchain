// Bound helpers for cascade-only permutations whose cascade position comes
// from the full-resolution depth buffer while temporal reprojection remains
// anchored to the HZB surface.
#include "indirect_cascade_upscale_cascade_bound.hlsl"

float2 BoundUpscaleClipPosition(float2 unscaledUv)
{
  float2 clipPosition =
      unscaledUv * float2(1.0, -1.0) + float2(0.0, 1.0);
  return clipPosition * float2(2.0, 2.0) + float2(-1.0, -1.0);
}

float3 ReconstructBoundPerspectiveCascadePosition(
    float2 unscaledUv, float viewDepth)
{
  float2 clipPosition = BoundUpscaleClipPosition(unscaledUv);
  float3 viewPosition = float3(
      cb_vNearFarViewCorner.zw * clipPosition * viewDepth,
      -viewDepth);
  return TransformUpscalePosition(viewToWorld, viewPosition);
}

float3 ReconstructBoundOrthoCascadePosition(
    float2 unscaledUv, float viewDepth)
{
  float2 clipPosition = BoundUpscaleClipPosition(unscaledUv);
  float3 viewPosition = float3(
      cb_vNearFarViewCorner.zw * clipPosition + cb_vViewTranslate.xy,
      -viewDepth);
  return TransformUpscalePosition(viewToWorld, viewPosition);
}

UpscaleCascadeSurface GatherBoundOrthoCascadeSurface(
    float2 unscaledUv, int2 pixel, float viewDepth)
{
  float2 clipPosition = BoundUpscaleClipPosition(unscaledUv);

  UpscaleCascadeSurface result;
  result.pixel = pixel;
  result.viewDepth = viewDepth;
  result.viewPosition = float3(
      cb_vNearFarViewCorner.zw * clipPosition + cb_vViewTranslate.xy,
      -viewDepth);
  result.worldPosition =
      TransformUpscalePosition(viewToWorld, result.viewPosition);
  result.normal = DecodeUpscaleNormal(
      tNormal.Load(int3(pixel, 0)).xy);
  return result;
}

float EvaluateBoundLowDepthCascadeOnlyLighting(
    UpscaleCascadeSurface hzbSurface,
    float3 sceneWorldPosition,
    float sceneDepth)
{
  float lightFacing = dot(
      hzbSurface.normal, cb_vDirectionalLightDirectionView.xyz);
  if (!(lightFacing < 0.330000013))
    return 0.0;

  float cameraRangeFade =
      -sceneDepth * cb_vInverseCameraRange.x + 1.0;
  UpscaleCascadeSelection activeCascade = SelectUpscaleCascade(
      sceneWorldPosition,
      cb_arrCascades[0], cb_arrCascades[1],
      cb_arrCascades[2], cb_arrCascades[3]);
  float visibility = EvaluateUpscaleLowCascadeShadow(
      taCascades, sShadowSamplerLinear_s, activeCascade,
      sceneWorldPosition, cameraRangeFade,
      cb_vCascadeSplits, cb_vCascadeSize, cb_vCascadePixelSize,
      cb_arrCascades[1], cb_arrCascades[2], cb_arrCascades[3]);
  return ApplyUpscaleDirectionalFacing(
      visibility, hzbSurface.normal,
      cb_vDirectionalLightDirectionView.xyz);
}

float EvaluateBoundMediumDepthCascadeOnlyLighting(
    UpscaleCascadeSurface hzbSurface,
    float3 sceneWorldPosition,
    float sceneDepth)
{
  float lightFacing = dot(
      hzbSurface.normal, cb_vDirectionalLightDirectionView.xyz);
  if (!(lightFacing < 0.330000013))
    return 0.0;

  float cameraRangeFade =
      -sceneDepth * cb_vInverseCameraRange.x + 1.0;
  UpscaleCascadeSelection activeCascade = SelectUpscaleCascade(
      sceneWorldPosition,
      cb_arrCascades[0], cb_arrCascades[1],
      cb_arrCascades[2], cb_arrCascades[3]);
  float visibility = EvaluateUpscaleMediumCascadeShadow(
      taCascades, sShadowSamplerLinear_s, activeCascade,
      sceneWorldPosition, cameraRangeFade,
      cb_vCascadeSplits, cb_vCascadeSize, cb_vCascadePixelSize,
      cb_arrCascades[1], cb_arrCascades[2], cb_arrCascades[3]);
  return ApplyUpscaleDirectionalFacing(
      visibility, hzbSurface.normal,
      cb_vDirectionalLightDirectionView.xyz);
}
