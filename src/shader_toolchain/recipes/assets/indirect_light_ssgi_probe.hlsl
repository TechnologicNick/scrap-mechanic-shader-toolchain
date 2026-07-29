// Perspective temporal SSGI/probe composition with policy-controlled AO.
#include "indirect_light_ortho_ssgi.hlsl"

struct IndirectLightSsgiProbeResult
{
  float4 indirect;
  float temporalConfidence;
  float4 occlusion;
};

IndirectLightSsgiProbeResult EvaluateIndirectLightSsgiProbePolicy(
    float2 unscaledUv,
    float qualityRadiusScale,
    bool enableScreenAo,
    uint subsurfaceLayerCount)
{
  IndirectLightSsgiProbeResult result;
  result.indirect = float4(0.0, 0.0, 0.0, 1.0);
  result.temporalConfidence = 1.0;
  result.occlusion = 1.0;
  IndirectLightSurface surface = LoadIndirectLightSurface(unscaledUv);
  if (surface.depth >= cb_vNearFarViewCorner.y - 1.0)
    return result;

  bool receivesIndirect = surface.material.z < 0.941176474;
  if (receivesIndirect && surface.depth < 500.0)
  {
    if (enableScreenAo)
      result.indirect.w = EvaluateIndirectLightAoQuality(
          surface, unscaledUv, qualityRadiusScale);
    result.occlusion = EvaluateIndirectLightSubsurfaceSet(
        surface, unscaledUv, subsurfaceLayerCount);
  }

  IndirectLightTemporalSample temporal =
      GatherIndirectLightTemporalSsgi(surface, unscaledUv);
  float3 viewPosition = float3(
      surface.viewCorner * surface.depth, -surface.depth);
  float3 worldPosition = TransformIndirectLightPosition(
      viewToWorld, viewPosition);
  float4 previousClip = mul(
      float4(worldPosition, 1.0), cb_xPrevWorldToViewProjection);
  float2 previousUv = previousClip.xy / previousClip.z;
  previousUv = previousUv * float2(0.5, -0.5) + 0.5;
  previousUv = min(cb_settings.vRenderScale,
      cb_settings.vRenderScale * previousUv);
  float volatility = abs(tVolatile.SampleLevel(
      PointClampClamp_s, previousUv, 0.0));
  float hitConfidence = 1.0 - saturate(abs(tHitCache.SampleLevel(
      PointClampClamp_s,
      min(cb_vPrevRenderScale, previousUv * cb_vPrevRenderScale), 0.0)));
  temporal.confidence *= saturate(cb_fRenderScaleStability
      * (1.0 - volatility * volatility) * hitConfidence);

  float3 viewDirection = normalize(viewPosition);
  float3 reflectionView = normalize(reflect(
      viewDirection, surface.normalView));
  float3 reflectionWorld = normalize(TransformIndirectLightDirection(
      viewToWorld, reflectionView));
  float3 normalWorld = normalize(TransformIndirectLightDirection(
      viewToWorld, surface.normalView));
  float reflectivity = 1.0 - surface.material.x;
  float roughness = max(surface.material.y, 0.25 * reflectivity);
  IndirectLightProbeAccumulation probes = GatherIndirectLightProbes(
      unscaledUv, surface.depth, worldPosition, reflectionWorld,
      normalWorld, roughness * 5.0, 1.0 - saturate(0.5 * roughness));
  float3 localReflection = probes.reflection
      / max(0.125, probes.reflectionWeight);
  float3 gpuReflection = probes.gpuReflection
      / max(0.001, probes.gpuReflectionWeight);
  float probeBlend = saturate(probes.reflectionWeight);
  float3 probeReflection = lerp(
      gpuReflection, localReflection, probeBlend * probeBlend);
  float3 probeGi = probes.diffuseGi / max(1.0, probes.diffuseGiWeight);
  float3 screenReflection = tSSR.SampleLevel(
      LinearClampClamp_s, surface.scaledUv, roughness * 5.0);
  float3 reflection = lerp(
      probeReflection, screenReflection, temporal.confidence);
  float3 diffuseIndirect = lerp(
      probeGi, temporal.radiance, temporal.confidence) * surface.diffuse;
  float reflectionEnergy = 1.0 - reflectivity * reflectivity;
  float3 indirect = diffuseIndirect + reflection * reflectionEnergy;
  indirect *= 0.884955764;
  indirect /= dot(indirect, float3(0.299, 0.587, 0.114)) * 0.2 + 1.4;
  result.indirect.xyz = ApplyIndirectLightMetalProfile(
      indirect, surface.diffuse, surface.neighborProfiles.x);
  if (enableScreenAo)
  {
    float probeAo = GatherIndirectLightProbeAo(
        unscaledUv, surface.depth, worldPosition, normalWorld);
    result.indirect.w = min(result.indirect.w,
        lerp(1.0, probeAo, temporal.confidence));
  }
  result.temporalConfidence = lerp(
      1.0, temporal.confidence, cb_settings.fInvSSGIKillSwitch);
  return result;
}

IndirectLightSsgiProbeResult EvaluateIndirectLightSsgiProbe(
    float2 unscaledUv,
    uint subsurfaceLayerCount)
{
  return EvaluateIndirectLightSsgiProbePolicy(
      unscaledUv, 1.0, false, subsurfaceLayerCount);
}
