// Orthographic reflection lighting with cascade-first counted visibility.
#define INDIRECT_LIGHT_ENABLE_TEMPORAL_SSGI 0
#define INDIRECT_LIGHT_ENABLE_PROBE_AO 0
#define INDIRECT_LIGHT_ENABLE_PROBE_GI 0
#include "indirect_light_ortho_ssgi.hlsl"
#include "indirect_light_cascade_visibility.hlsl"

IndirectLightOrthoMediumResult
EvaluateIndirectLightOrthoReflectionCascadePolicy(
    float2 unscaledUv,
    float qualityRadiusScale,
    bool enableScreenAo,
    uint outputCount)
{
  IndirectLightOrthoMediumResult result =
      EvaluateIndirectLightOrthoReflectionPolicy(
          unscaledUv, qualityRadiusScale, enableScreenAo, 0u);
  result.occlusion = 1.0;

  IndirectLightSurface surface = LoadIndirectLightOrthoSurface(unscaledUv);
  bool receivesIndirect = surface.depth < cb_vNearFarViewCorner.y - 1.0
      && surface.material.z < 0.941176474
      && surface.depth < 500.0;
  if (receivesIndirect)
    result.occlusion = EvaluateIndirectLightCascadeVisibilitySet(
        surface, unscaledUv, outputCount);
  return result;
}
