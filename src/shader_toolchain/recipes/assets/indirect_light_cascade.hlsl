// Perspective cascade visibility with optional clustered SSS channels.

#ifndef INDIRECT_LIGHT_CASCADE_OUTPUT_COUNT
#define INDIRECT_LIGHT_CASCADE_OUTPUT_COUNT 1
#endif

#define INDIRECT_LIGHT_ENABLE_PROBE_GI 0
#define INDIRECT_LIGHT_ENABLE_REFLECTION 0
#define INDIRECT_LIGHT_ENABLE_DIFFUSE 0
#if INDIRECT_LIGHT_CASCADE_OUTPUT_COUNT == 1
#include "indirect_light_cluster_abi.hlsl"
StructuredBuffer<uint> sbVoxelLightIds : register(t21);
#endif
#include "indirect_light_probe_cascade.hlsl"
#define INDIRECT_LIGHT_CASCADE_COMPILED_COUNT \
    INDIRECT_LIGHT_CASCADE_OUTPUT_COUNT
#include "indirect_light_cascade_visibility.hlsl"

struct IndirectLightCascadeResult
{
  float4 indirect;
  float subsurface;
  float4 visibility;
};

IndirectLightCascadeResult EvaluateIndirectLightCascadeVisibilityPolicy(
    float2 unscaledUv,
    float qualityRadiusScale,
    bool enableScreenAo)
{
  IndirectLightCascadeResult result;
  result.indirect = float4(0.0, 0.0, 0.0, 1.0);
  result.subsurface = 1.0;
  result.visibility = 1.0;

  IndirectLightSurface surface = LoadIndirectLightSurface(unscaledUv);
  if (surface.depth >= cb_vNearFarViewCorner.y - 1.0)
    return result;

  bool receivesIndirect = surface.material.z < 0.941176474
      && surface.depth < 500.0;
  if (!receivesIndirect)
    return result;

  if (enableScreenAo)
    result.indirect.w = EvaluateIndirectLightAoQuality(
        surface, unscaledUv, qualityRadiusScale);
  result.visibility = EvaluateIndirectLightCascadeVisibilitySet(
      surface, unscaledUv, INDIRECT_LIGHT_CASCADE_OUTPUT_COUNT);
  return result;
}

IndirectLightCascadeResult EvaluateIndirectLightCascadeVisibility(
    float2 unscaledUv)
{
  return EvaluateIndirectLightCascadeVisibilityPolicy(
      unscaledUv, 1.0, false);
}
