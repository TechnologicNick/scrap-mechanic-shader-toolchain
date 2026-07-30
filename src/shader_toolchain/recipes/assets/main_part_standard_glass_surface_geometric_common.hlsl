#define MAIN_PART_GLASS_SURFACE_GEOMETRIC_NORMAL_ONLY
#include "main_part_standard_glass_surface_unresponsive_common.hlsl"
#undef MAIN_PART_GLASS_SURFACE_GEOMETRIC_NORMAL_ONLY

void EvaluateMainPartStandardGeometricGlassSurface(
    float4 position, float3 viewPosition, float2 uv, float3 normalView,
    float4 vertexColor, float3 screenUv, float4 fogColor, uint frontFace,
    out float4 colorTarget, out float4 auxiliaryTarget)
{
  MainPartDissolveGlassMaterial material =
      EvaluateMainPartGlassMaterialGeometricNormal(
          viewPosition, uv, normalView, vertexColor, frontFace != 0);
  MainPartGlassLighting lighting =
      EvaluateMainPartLegacyGlassDirectionalLighting(viewPosition, material);
#ifdef MAIN_PART_STANDARD_GLASS_SINGLE_PROBE
  lighting.reflectedColor = EvaluateMainPartSingleReflection(material);
#elif defined(MAIN_PART_STANDARD_GLASS_OFF_AMBIENT)
  lighting.reflectedColor = material.gloss * 0.119999997;
#else
  lighting.reflectedColor = 0.0;
#endif
  MainPartGlassSurfaceComposite composite =
      ComposeMainPartStandardUnresponsiveGlassSurface(
          screenUv, fogColor, frontFace != 0, material, lighting);
  colorTarget = composite.color;
  auxiliaryTarget = composite.auxiliary;
}
