#define MAIN_PART_GLASS_SURFACE_HAS_DISSOLVE
#include "main_part_glass_surface_common.hlsl"
#undef MAIN_PART_GLASS_SURFACE_HAS_DISSOLVE

void EvaluateMainPartDissolveGlassSurfaceLow(
    float4 position,
    float3 viewPosition,
    float2 uv,
    float3 normalView,
    float3 tangentView,
    float3 bitangentView,
    float4 vertexColor,
    float3 screenUv,
    float4 fogColor,
    float cutoffOffset,
    uint frontFace,
    out float4 colorTarget,
    out float4 auxiliaryTarget)
{
  MainPartDissolveGlassMaterial material =
      EvaluateMainPartDissolveGlassMaterial(
          viewPosition, uv, normalView, tangentView, bitangentView,
          vertexColor, cutoffOffset, frontFace != 0);
  MainPartGlassLighting lighting =
      EvaluateMainPartGlassDirectionalLighting(viewPosition, material);
  lighting.reflectedColor = 0.0;
  MainPartGlassSurfaceComposite composite =
      ComposeMainPartDissolveGlassSurface(
          screenUv, fogColor, frontFace != 0, material, lighting);
  colorTarget = composite.color;
  auxiliaryTarget = composite.auxiliary;
}
