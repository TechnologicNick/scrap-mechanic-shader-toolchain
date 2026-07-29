// Orthographic horizon AO with optional clustered subsurface visibility.
#define INDIRECT_LIGHT_ENABLE_TEMPORAL_SSGI 0
#define INDIRECT_LIGHT_ENABLE_PROBE_AO 0
#define INDIRECT_LIGHT_ENABLE_PROBE_GI 0
#define INDIRECT_LIGHT_ENABLE_REFLECTION 0
#define INDIRECT_LIGHT_ENABLE_DIFFUSE 0
#include "indirect_light_ortho_ssgi.hlsl"

struct IndirectLightOrthoAoSssResult
{
  float4 ambientOcclusion;
  float subsurface;
  float4 occlusion;
};

IndirectLightOrthoAoSssResult EvaluateIndirectLightOrthoAoSss(
    float2 unscaledUv,
    float qualityRadiusScale,
    uint subsurfaceLayerCount)
{
  IndirectLightOrthoAoSssResult result;
  result.ambientOcclusion = float4(0.0, 0.0, 0.0, 1.0);
  result.subsurface = 1.0;
  result.occlusion = 1.0;

  IndirectLightSurface surface = LoadIndirectLightOrthoSurface(unscaledUv);
  if (surface.depth >= cb_vNearFarViewCorner.y - 1.0)
    return result;
  bool receivesIndirect = surface.material.z < 0.941176474
      && surface.depth < 500.0;
  if (!receivesIndirect)
    return result;

  result.ambientOcclusion.w = EvaluateIndirectLightOrthoAoQuality(
      surface, unscaledUv, qualityRadiusScale);
  if (subsurfaceLayerCount > 0u)
    result.occlusion = EvaluateIndirectLightSubsurfaceSet(
        surface, unscaledUv, subsurfaceLayerCount);
  return result;
}
