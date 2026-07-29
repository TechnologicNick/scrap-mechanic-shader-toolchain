// Perspective medium-AO policy with clustered probes and counted SSS layers.
#include "indirect_light_ortho_ssgi.hlsl"
#include "indirect_light_cascade_visibility.hlsl"

struct IndirectLightMediumProbeResult
{
  float4 indirectAo;
  float subsurface;
  float4 occlusion;
};

float EvaluateIndirectLightProbeAoQuality(
    IndirectLightSurface surface,
    float2 unscaledUv,
    float qualityRadiusScale)
{
  uint2 aoSize = max(1u, cb_settings.vuSize);
  float2 quantizedUv = floor(cb_settings.vInvRenderScale
      * surface.scaledUv * (float2)aoSize) / (float2)aoSize;
  float3 center = LoadIndirectLightAoViewPosition(quantizedUv, aoSize);
  center += surface.normalView * 0.03;
  float3 viewDirection = normalize(center);
  float projectedRadius = max(3.0,
      (2.0 * cb_settings.vStart.x * cb_settings.fProjectionScale)
      * qualityRadiusScale / max(0.01, surface.depth) / 3.0);
  float noise = abs(frac(cb_fTime * 0.1
      + tScreenNoise.Load(uint3((uint2)(cb_vTargetSize * unscaledUv) & 63u, 0)))
      - 0.5);
  float initialRadius = saturate(0.25 * surface.depth - 1.0)
      * projectedRadius + frac(noise * projectedRadius) * 0.8;
  float ao = 0.0;
  [unroll]
  for (uint slice = 0u; slice < 3u; ++slice)
  {
    float angle = 2.09439516 * (float)slice;
    float sine;
    float cosine;
    sincos(angle, sine, cosine);
    ao += EvaluateIndirectLightHorizonSlice(
        surface.scaledUv, aoSize, center, viewDirection, surface.normalView,
        float2(cosine, sine), initialRadius + projectedRadius,
        projectedRadius);
  }
  ao *= 1.0 / 3.0;
  float depthFade = saturate(0.002 * surface.depth);
  ao = 1.0 - (1.0 - ao) * (1.0 - depthFade * depthFade);
  return pow(max(1.0e-4, ao), cb_settings.vAdd.y);
}

IndirectLightMediumProbeResult EvaluateIndirectLightProbePolicy(
    float2 unscaledUv,
    float qualityRadiusScale,
    bool enableScreenAo,
    uint subsurfaceLayerCount)
{
  IndirectLightMediumProbeResult result;
  result.indirectAo = float4(0.0, 0.0, 0.0, 1.0);
  result.subsurface = 1.0;
  result.occlusion = 1.0;
  IndirectLightSurface surface = LoadIndirectLightSurface(unscaledUv);
  if (surface.depth >= cb_vNearFarViewCorner.y - 1.0)
    return result;

  bool receivesIndirect = surface.material.z < 0.941176474
      && surface.depth < 500.0;
  if (receivesIndirect)
  {
    if (enableScreenAo)
      result.indirectAo.w = EvaluateIndirectLightProbeAoQuality(
          surface, unscaledUv, qualityRadiusScale);
    if (subsurfaceLayerCount > 0u)
      result.occlusion = EvaluateIndirectLightSubsurfaceSet(
          surface, unscaledUv, subsurfaceLayerCount);
  }

  float3 viewPosition = float3(
      surface.viewCorner * surface.depth, -surface.depth);
  float3 worldPosition = TransformIndirectLightPosition(viewToWorld, viewPosition);
  float3 viewDirection = normalize(viewPosition);
  float3 reflectionView = normalize(reflect(viewDirection, surface.normalView));
  float3 reflectionWorld = normalize(TransformIndirectLightDirection(
      viewToWorld, reflectionView));
  float3 normalWorld = normalize(TransformIndirectLightDirection(
      viewToWorld, surface.normalView));
  float reflectivity = 1.0 - surface.material.x;
  float roughness = max(surface.material.y, 0.25 * reflectivity);
  IndirectLightProbeAccumulation probes = GatherIndirectLightProbes(
      unscaledUv, surface.depth, worldPosition, reflectionWorld,
      normalWorld, roughness * 5.0, 1.0 - saturate(0.5 * roughness));
  float3 reflection = probes.reflection
      / max(0.125, probes.reflectionWeight);
  float3 gpuReflection = probes.gpuReflection
      / max(0.001, probes.gpuReflectionWeight);
  float reflectionBlend = saturate(probes.reflectionWeight);
  reflection = lerp(gpuReflection, reflection,
      reflectionBlend * reflectionBlend);
  float3 diffuseGi = probes.diffuseGi / max(1.0, probes.diffuseGiWeight);
  float reflectionEnergy = 1.0 - reflectivity * reflectivity;
  result.indirectAo.xyz = diffuseGi * surface.diffuse
      + reflection * reflectionEnergy;
  result.indirectAo.xyz *= 0.884955764;
  float compression = dot(result.indirectAo.xyz,
      float3(0.299, 0.587, 0.114)) * 0.2 + 1.4;
  result.indirectAo.xyz /= compression;
  result.indirectAo.xyz = ApplyIndirectLightMetalProfile(
      result.indirectAo.xyz, surface.diffuse, surface.neighborProfiles.x);
#if INDIRECT_LIGHT_ENABLE_PROBE_AO
  if (enableScreenAo)
  {
    float probeAo = GatherIndirectLightProbeAo(
        unscaledUv, surface.depth, worldPosition, normalWorld);
    result.indirectAo.w = min(result.indirectAo.w, probeAo);
  }
#endif
  return result;
}

IndirectLightMediumProbeResult EvaluateIndirectLightProbeQuality(
    float2 unscaledUv,
    uint subsurfaceLayerCount,
    float qualityRadiusScale)
{
  return EvaluateIndirectLightProbePolicy(
      unscaledUv, qualityRadiusScale, true, subsurfaceLayerCount);
}

IndirectLightMediumProbeResult EvaluateIndirectLightMediumProbe(
    float2 unscaledUv,
    uint subsurfaceLayerCount)
{
  return EvaluateIndirectLightProbeQuality(
      unscaledUv, subsurfaceLayerCount, 1.0);
}

IndirectLightMediumProbeResult EvaluateIndirectLightOrthoHighCascadeProbe(
    float2 unscaledUv)
{
  IndirectLightMediumProbeResult result;
  result.indirectAo = float4(0.0, 0.0, 0.0, 1.0);
  result.subsurface = 1.0;
  result.occlusion = 1.0;
  IndirectLightSurface surface = LoadIndirectLightOrthoSurface(unscaledUv);
  if (surface.depth >= cb_vNearFarViewCorner.y - 1.0)
    return result;

  bool receivesIndirect = surface.material.z < 0.941176474
      && surface.depth < 500.0;
  if (receivesIndirect)
  {
    result.indirectAo.w = EvaluateIndirectLightOrthoMediumAo(
        surface, unscaledUv);
    float directionalFacing = dot(
        surface.normalView, cb_vDirectionalLightDirectionView);
    if (directionalFacing < 0.330000013)
      result.occlusion.x = lerp(1.0,
          TraceIndirectLightCascade(surface, directionalFacing),
          cb_settings.fInvSSGIKillSwitch);
  }

  float3 viewPosition = IndirectLightOrthoViewPosition(surface, surface.depth);
  float3 worldPosition = TransformIndirectLightPosition(viewToWorld, viewPosition);
  float3 viewDirection = normalize(viewPosition);
  float3 reflectionView = normalize(reflect(viewDirection, surface.normalView));
  float3 reflectionWorld = normalize(TransformIndirectLightDirection(
      viewToWorld, reflectionView));
  float3 normalWorld = normalize(TransformIndirectLightDirection(
      viewToWorld, surface.normalView));
  float reflectivity = 1.0 - surface.material.x;
  float roughness = max(surface.material.y, 0.25 * reflectivity);
  IndirectLightProbeAccumulation probes = GatherIndirectLightProbes(
      unscaledUv, surface.depth, worldPosition, reflectionWorld,
      normalWorld, roughness * 5.0, 1.0 - saturate(0.5 * roughness));
  float3 reflection = probes.reflection
      / max(0.125, probes.reflectionWeight);
  float3 gpuReflection = probes.gpuReflection
      / max(0.001, probes.gpuReflectionWeight);
  float reflectionBlend = saturate(probes.reflectionWeight);
  reflection = lerp(gpuReflection, reflection,
      reflectionBlend * reflectionBlend);
  float3 diffuseGi = probes.diffuseGi / max(1.0, probes.diffuseGiWeight);
  float reflectionEnergy = 1.0 - reflectivity * reflectivity;
  result.indirectAo.xyz = diffuseGi * surface.diffuse
      + reflection * reflectionEnergy;
  result.indirectAo.xyz *= 0.884955764;
  float compression = dot(result.indirectAo.xyz,
      float3(0.299, 0.587, 0.114)) * 0.2 + 1.4;
  result.indirectAo.xyz /= compression;
  result.indirectAo.xyz = ApplyIndirectLightMetalProfile(
      result.indirectAo.xyz, surface.diffuse, surface.neighborProfiles.x);
#if INDIRECT_LIGHT_ENABLE_PROBE_AO
  float probeAo = GatherIndirectLightProbeAo(
      unscaledUv, surface.depth, worldPosition, normalWorld);
  result.indirectAo.w = min(result.indirectAo.w, probeAo);
#endif
  return result;
}

IndirectLightMediumProbeResult EvaluateIndirectLightOrthoProbePolicy(
    float2 unscaledUv,
    float qualityRadiusScale,
    bool enableScreenAo,
    uint subsurfaceLayerCount)
{
  IndirectLightMediumProbeResult result;
  result.indirectAo = float4(0.0, 0.0, 0.0, 1.0);
  result.subsurface = 1.0;
  result.occlusion = 1.0;
  IndirectLightSurface surface = LoadIndirectLightOrthoSurface(unscaledUv);
  if (surface.depth >= cb_vNearFarViewCorner.y - 1.0)
    return result;

  bool receivesIndirect = surface.material.z < 0.941176474
      && surface.depth < 500.0;
  if (receivesIndirect)
  {
    if (enableScreenAo)
      result.indirectAo.w = EvaluateIndirectLightOrthoAoQuality(
          surface, unscaledUv, qualityRadiusScale);
    if (subsurfaceLayerCount > 0u)
      result.occlusion = EvaluateIndirectLightSubsurfaceSet(
          surface, unscaledUv, subsurfaceLayerCount);
  }

  float3 viewPosition = IndirectLightOrthoViewPosition(
      surface, surface.depth);
  float3 worldPosition = TransformIndirectLightPosition(
      viewToWorld, viewPosition);
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
  float3 reflection = probes.reflection
      / max(0.125, probes.reflectionWeight);
  float3 gpuReflection = probes.gpuReflection
      / max(0.001, probes.gpuReflectionWeight);
  float reflectionBlend = saturate(probes.reflectionWeight);
  reflection = lerp(gpuReflection, reflection,
      reflectionBlend * reflectionBlend);
  float3 diffuseGi = probes.diffuseGi / max(1.0, probes.diffuseGiWeight);
  float reflectionEnergy = 1.0 - reflectivity * reflectivity;
  result.indirectAo.xyz = diffuseGi * surface.diffuse
      + reflection * reflectionEnergy;
  result.indirectAo.xyz *= 0.884955764;
  float compression = dot(result.indirectAo.xyz,
      float3(0.299, 0.587, 0.114)) * 0.2 + 1.4;
  result.indirectAo.xyz /= compression;
  result.indirectAo.xyz = ApplyIndirectLightMetalProfile(
      result.indirectAo.xyz, surface.diffuse, surface.neighborProfiles.x);
#if INDIRECT_LIGHT_ENABLE_PROBE_AO
  if (enableScreenAo)
  {
    float probeAo = GatherIndirectLightProbeAo(
        unscaledUv, surface.depth, worldPosition, normalWorld);
    result.indirectAo.w = min(result.indirectAo.w, probeAo);
  }
#endif
  return result;
}

IndirectLightMediumProbeResult EvaluateIndirectLightOrthoProbeCascadePolicy(
    float2 unscaledUv,
    float qualityRadiusScale,
    bool enableScreenAo,
    uint outputCount)
{
  IndirectLightMediumProbeResult result = EvaluateIndirectLightOrthoProbePolicy(
      unscaledUv, qualityRadiusScale, enableScreenAo, 0u);
  result.occlusion = 1.0;
  if (outputCount == 0u)
    return result;

  IndirectLightSurface surface = LoadIndirectLightOrthoSurface(unscaledUv);
  bool receivesIndirect = surface.depth < cb_vNearFarViewCorner.y - 1.0
      && surface.material.z < 0.941176474
      && surface.depth < 500.0;
  if (receivesIndirect)
    result.occlusion = EvaluateIndirectLightCascadeVisibilitySet(
        surface, unscaledUv, outputCount);
  return result;
}
