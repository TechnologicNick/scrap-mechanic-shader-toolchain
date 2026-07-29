// Orthographic horizon AO with cascade-first counted visibility outputs.
#define INDIRECT_LIGHT_ENABLE_TEMPORAL_SSGI 0
#define INDIRECT_LIGHT_ENABLE_PROBE_AO 0
#define INDIRECT_LIGHT_ENABLE_PROBE_GI 0
#define INDIRECT_LIGHT_ENABLE_REFLECTION 0
#define INDIRECT_LIGHT_ENABLE_DIFFUSE 0
#include "indirect_light_ortho_ssgi.hlsl"
#include "indirect_light_cascade_visibility.hlsl"

struct IndirectLightOrthoCascadeResult
{
  float4 ambientOcclusion;
  float subsurface;
  float4 visibility;
};

IndirectLightOrthoCascadeResult EvaluateIndirectLightOrthoCascade(
    float2 unscaledUv,
    float qualityRadiusScale,
    uint outputCount)
{
  IndirectLightOrthoCascadeResult result;
  result.ambientOcclusion = float4(0.0, 0.0, 0.0, 1.0);
  result.subsurface = 1.0;
  result.visibility = 1.0;

  IndirectLightSurface surface = LoadIndirectLightOrthoSurface(unscaledUv);
  if (surface.depth >= cb_vNearFarViewCorner.y - 1.0)
    return result;
  bool receivesIndirect = surface.material.z < 0.941176474
      && surface.depth < 500.0;
  if (!receivesIndirect)
    return result;

  result.ambientOcclusion.w = EvaluateIndirectLightOrthoAoQuality(
      surface, unscaledUv, qualityRadiusScale);
  result.visibility = EvaluateIndirectLightCascadeVisibilitySet(
      surface, unscaledUv, outputCount);
  return result;
}
