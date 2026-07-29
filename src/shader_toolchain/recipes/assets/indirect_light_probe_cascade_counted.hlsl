// Probe/reflection lighting with optional cascade-first visibility outputs.

#ifndef INDIRECT_LIGHT_PROBE_CASCADE_COUNT
#define INDIRECT_LIGHT_PROBE_CASCADE_COUNT 0
#endif

#ifndef INDIRECT_LIGHT_ENABLE_TEMPORAL_SSGI
#define INDIRECT_LIGHT_ENABLE_TEMPORAL_SSGI 0
#endif

#ifndef INDIRECT_LIGHT_ENABLE_PROBE_AO
#define INDIRECT_LIGHT_ENABLE_PROBE_AO 0
#endif

#define INDIRECT_LIGHT_CASCADE_COMPILED_COUNT \
    INDIRECT_LIGHT_PROBE_CASCADE_COUNT
#include "indirect_light_ortho_ssgi.hlsl"
#include "indirect_light_cascade_visibility.hlsl"

struct IndirectLightProbeCascadeCountedResult
{
  float4 indirect;
  float subsurface;
  float4 visibility;
};

IndirectLightProbeCascadeCountedResult
EvaluateIndirectLightCountedProbeCascadePolicy(
    float2 unscaledUv,
    float qualityRadiusScale,
    bool enableScreenAo)
{
  IndirectLightProbeCascadeCountedResult result;
  result.indirect = float4(0.0, 0.0, 0.0, 1.0);
  result.subsurface = 1.0;
  result.visibility = 1.0;

#if INDIRECT_LIGHT_PROBE_CASCADE_COUNT > 0
  IndirectLightResult base = EvaluateIndirectLightProbeCascade(unscaledUv);
  result.indirect = base.indirect;
  result.subsurface = base.subsurface;
  result.visibility.x = base.cascadeOcclusion;
#else
  IndirectLightSurface surface = LoadIndirectLightSurface(unscaledUv);
  if (surface.depth >= cb_vNearFarViewCorner.y - 1.0)
    return result;

  if (surface.material.z < 0.941176474)
  {
    float materialCoverage = 1.0 - pow(abs(1.0 - surface.material.y), 0.75);
    materialCoverage = saturate((3.6 * materialCoverage * surface.material.x
                                - 0.15) / 0.7);
    float roughness = surface.material.z * 0.15 + 0.125;
    float luminance = max(0.3, dot(surface.diffuse,
        float3(0.299, 0.587, 0.114)));
    float reflectionStrength = saturate(
        (1.0 - luminance) * (1.0 - luminance) * roughness
        + materialCoverage);
    float diffuseStrength = (1.0 - materialCoverage)
        * lerp(1.0 - (1.0 - cb_fDirectionalLightIntensity)
                       * (1.0 - cb_fDirectionalLightIntensity),
               1.0, 0.4);

    if (surface.depth < cb_cluster.fClusterMaxFarReflections)
    {
      float3 viewPosition = float3(surface.viewCorner * surface.depth,
                                   -surface.depth);
      float3 worldPosition = TransformIndirectLightPosition(
          viewToWorld, viewPosition);
      float3 viewDirection = normalize(viewPosition);
      float3 reflectionView = viewDirection
          - 2.0 * dot(viewDirection, surface.normalView) * surface.normalView;
      float3 reflectionWorld = normalize(TransformIndirectLightDirection(
          viewToWorld, reflectionView));
      float3 normalWorld = TransformIndirectLightDirection(
          viewToWorld, surface.normalView);
      float roughnessMip = max(surface.material.z,
                               0.25 * (1.0 - surface.material.y));
      float fallbackWeight = 1.0 - saturate(0.5 * roughnessMip);
      IndirectLightProbeAccumulation probes = GatherIndirectLightProbes(
          unscaledUv, surface.depth, worldPosition, reflectionWorld,
          normalWorld, roughnessMip, fallbackWeight);
      float3 reflection = probes.reflection / max(0.125,
          probes.gpuReflectionWeight);
      float3 gpuReflection = probes.gpuReflection / max(0.001,
          probes.reflectionWeight);
      float gpuBlend = saturate(probes.reflectionWeight);
      reflection = lerp(gpuReflection, reflection, gpuBlend * gpuBlend);
      float3 diffuseGi = probes.diffuseGi / max(1.0, probes.diffuseGiWeight);
      result.indirect.xyz = reflectionStrength * reflection
          + diffuseStrength * diffuseGi;
    }
  }

  result.indirect.xyz *= 0.884955764;
  float compression = dot(result.indirect.xyz,
      float3(0.299, 0.587, 0.114)) * 0.2 + 1.4;
  result.indirect.xyz /= compression;
  result.indirect.xyz = ApplyIndirectLightMetalProfile(
      result.indirect.xyz, surface.diffuse, surface.neighborProfiles.x);
#endif

  IndirectLightSurface visibilitySurface = LoadIndirectLightSurface(unscaledUv);
  bool receivesIndirect =
      visibilitySurface.depth < cb_vNearFarViewCorner.y - 1.0
      && visibilitySurface.material.z < 0.941176474
      && visibilitySurface.depth < 500.0;
#if INDIRECT_LIGHT_PROBE_CASCADE_COUNT > 0
  if (receivesIndirect)
    result.visibility = EvaluateIndirectLightCascadeVisibilitySet(
        visibilitySurface, unscaledUv, INDIRECT_LIGHT_PROBE_CASCADE_COUNT);
#endif

  if (receivesIndirect && enableScreenAo)
    result.indirect.w = EvaluateIndirectLightAoQuality(
        visibilitySurface, unscaledUv, qualityRadiusScale);
#if INDIRECT_LIGHT_ENABLE_PROBE_AO
  if (enableScreenAo)
  {
    float3 viewPosition = float3(
        visibilitySurface.viewCorner * visibilitySurface.depth,
        -visibilitySurface.depth);
    float3 worldPosition = TransformIndirectLightPosition(
        viewToWorld, viewPosition);
    float3 normalWorld = normalize(TransformIndirectLightDirection(
        viewToWorld, visibilitySurface.normalView));
    float probeAo = GatherIndirectLightProbeAo(
        unscaledUv, visibilitySurface.depth, worldPosition, normalWorld);
    result.indirect.w = min(result.indirect.w, probeAo);
  }
#endif
  return result;
}

IndirectLightProbeCascadeCountedResult
EvaluateIndirectLightCountedProbeCascade(float2 unscaledUv)
{
  return EvaluateIndirectLightCountedProbeCascadePolicy(
      unscaledUv, 1.0, false);
}
