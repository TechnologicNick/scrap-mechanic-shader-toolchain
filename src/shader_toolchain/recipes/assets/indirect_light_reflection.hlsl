// Perspective reflection-only indirect lighting with optional horizon AO and
// a counted set of clustered subsurface-visibility outputs.
#define INDIRECT_LIGHT_ENABLE_TEMPORAL_SSGI 0
#define INDIRECT_LIGHT_ENABLE_PROBE_AO 0
#define INDIRECT_LIGHT_ENABLE_PROBE_GI 0
#include "indirect_light_ortho_ssgi.hlsl"

struct IndirectLightReflectionResult
{
  float4 indirectAo;
  float subsurface;
  float4 occlusion;
};

IndirectLightReflectionResult EvaluateIndirectLightReflectionPolicy(
    float2 unscaledUv,
    float qualityRadiusScale,
    bool enableScreenAo,
    uint subsurfaceLayerCount)
{
  IndirectLightReflectionResult result;
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
      result.indirectAo.w = EvaluateIndirectLightAoQuality(
          surface, unscaledUv, qualityRadiusScale);
    if (subsurfaceLayerCount > 0u)
      result.occlusion = EvaluateIndirectLightSubsurfaceSet(
          surface, unscaledUv, subsurfaceLayerCount);
  }

  result.indirectAo.xyz = EvaluateIndirectLightReflectionOnly(
      surface, unscaledUv);
  result.indirectAo.xyz *= 0.884955764;
  float compression = dot(result.indirectAo.xyz,
      float3(0.299, 0.587, 0.114)) * 0.2 + 1.4;
  result.indirectAo.xyz /= compression;
  result.indirectAo.xyz = ApplyIndirectLightMetalProfile(
      result.indirectAo.xyz, surface.diffuse, surface.neighborProfiles.x);
  return result;
}
