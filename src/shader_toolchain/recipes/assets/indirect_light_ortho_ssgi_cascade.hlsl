// Orthographic temporal SSGI with cascade-first counted visibility.
#include "indirect_light_ssgi_cascade.hlsl"

IndirectLightSsgiCascadeResult EvaluateIndirectLightOrthoSsgiCascade(
    float2 unscaledUv,
    float qualityRadiusScale,
    bool enableScreenAo,
    uint occlusionOutputCount)
{
  IndirectLightOrthoSsgiResult base = EvaluateIndirectLightOrthoSsgiPolicy(
      unscaledUv, 0u, qualityRadiusScale, enableScreenAo);

  IndirectLightSsgiCascadeResult result;
  result.indirectAo = base.indirectAo;
  result.temporalConfidence = base.temporalConfidence;
  result.occlusion = 1.0;
  if (occlusionOutputCount == 0u)
    return result;

  IndirectLightSurface surface = LoadIndirectLightOrthoSurface(unscaledUv);
  bool receivesIndirect = surface.depth < cb_vNearFarViewCorner.y - 1.0
      && surface.material.z < 0.941176474
      && surface.depth < 500.0;
  if (receivesIndirect)
  {
    result.occlusion = EvaluateIndirectLightCascadeOcclusionSet(
        surface, unscaledUv, occlusionOutputCount);
  }
  return result;
}
