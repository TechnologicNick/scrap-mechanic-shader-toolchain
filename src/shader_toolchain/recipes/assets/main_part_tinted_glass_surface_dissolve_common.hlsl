#define MAIN_PART_GLASS_SURFACE_HAS_DISSOLVE
#include "main_part_legacy_glass_surface_basic.hlsl"

void EvaluateMainPartTintedDissolveGlassSurface(
    float4 position, float3 viewPosition, float2 materialUv, float2 dissolveUv,
    float3 normalView, float3 tangentView, float3 bitangentView,
    float4 vertexColor, float3 screenUv, float4 fogColor, float cutoffOffset,
    uint frontFace, out float4 colorTarget, out float4 auxiliaryTarget)
{
  MainPartDissolveGlassMaterial material =
      EvaluateMainPartDissolveGlassMaterialAtUv(
          viewPosition, materialUv, dissolveUv, normalView, tangentView,
          bitangentView, vertexColor, cutoffOffset, frontFace != 0);
  MainPartGlassLighting lighting =
      EvaluateMainPartLegacyGlassDirectionalLighting(viewPosition, material);
#ifdef MAIN_PART_TINTED_GLASS_SINGLE_PROBE
  lighting.reflectedColor = EvaluateMainPartSingleReflection(material);
#elif defined(MAIN_PART_TINTED_GLASS_OFF_AMBIENT)
  lighting.reflectedColor = material.gloss * 0.119999997;
#else
  lighting.reflectedColor = 0.0;
#endif
  MainPartGlassSurfaceComposite composite = ComposeMainPartLegacyGlassSurface(
      screenUv, fogColor, frontFace != 0, material, lighting);
  colorTarget = composite.color;
  auxiliaryTarget = composite.auxiliary;
}
#undef MAIN_PART_GLASS_SURFACE_HAS_DISSOLVE
