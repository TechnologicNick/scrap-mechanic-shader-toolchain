#define MAIN_PART_GLASS_SURFACE_NO_CUTOUT
#include "main_part_glass_surface_common.hlsl"

void EvaluateMainPartGlassSurfaceLowNoCutout(
    float4 position, float3 viewPosition, float2 uv, float3 normalView,
    float3 tangentView, float3 bitangentView, float4 vertexColor,
    float3 screenUv, float4 fogColor, uint frontFace,
    out float4 colorTarget, out float4 auxiliaryTarget)
{
  MainPartDissolveGlassMaterial material = EvaluateMainPartGlassMaterialNoCutout(
      viewPosition, uv, normalView, tangentView, bitangentView,
      vertexColor, frontFace != 0);
  MainPartGlassLighting lighting =
      EvaluateMainPartGlassDirectionalLighting(viewPosition, material);
  lighting.reflectedColor = 0.0;
  MainPartGlassSurfaceComposite composite = ComposeMainPartDissolveGlassSurface(
      screenUv, fogColor, frontFace != 0, material, lighting);
  colorTarget = composite.color;
  auxiliaryTarget = composite.auxiliary;
}
#undef MAIN_PART_GLASS_SURFACE_NO_CUTOUT
