#include "main_part_glass_surface_common.hlsl"

MainPartGlassSurfaceComposite ComposeMainPartTintedTransmissionGlassSurface(
    float3 screenUv, float4 fogColor, bool frontFace,
    MainPartDissolveGlassMaterial material, MainPartGlassLighting lighting)
{
  MainPartGlassSurfaceComposite result;
  lighting.directColor = material.coverage * (1.0 - lighting.directColor)
      + lighting.directColor;
  float auxiliaryCoverage = min(0.5, 0.5 * material.coverage);

  float normalFacing = dot(material.viewDirection, material.normalView);
  float minimumFresnel = material.gloss * 0.5 + 0.00999999978;
  float grazing = 1.0 - normalFacing;
  float fresnel = grazing * grazing;
  fresnel *= fresnel;
  fresnel *= grazing;
  fresnel = (1.0 - minimumFresnel) * fresnel + minimumFresnel;

  float faceTransparency = frontFace
      ? cb_glass.fTransparencyFront : cb_glass.fTransparencyBack;
  float transparency = saturate(
      faceTransparency + lighting.specular + fresnel);
  float reflectionEnergy = lighting.specular + fresnel;
  float4 frame = tFrame.SampleLevel(
      LinearMirrorMirror_s, ClampMainPartFrameUv(screenUv.xy), 0);
  float3 glassColor = (material.diffuseColor * frame.xyz - frame.xyz)
      * transparency + frame.xyz;
  glassColor += lighting.directColor * reflectionEnergy;
  glassColor += lighting.reflectedColor;

  float fogStrength = 0.349999994 * auxiliaryCoverage;
  fogStrength *= 1.0 - min(1.0, 0.00999999978 * material.viewDistance);
  float largestChannel = max(abs(glassColor.x), abs(glassColor.y));
  largestChannel = max(largestChannel, abs(glassColor.z));
  fogStrength = (1.0 - fogStrength * largestChannel) * fogColor.w;
  result.color.xyz = (fogColor.xyz - glassColor) * fogStrength + glassColor;
  result.color.w = max(frame.w, transparency);
  result.auxiliary = float4(
      auxiliaryCoverage, 0.0, 0.0, result.color.w);
  return result;
}

void EvaluateMainPartTintedTransmissionGlassSurface(
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
#ifdef MAIN_PART_TINTED_GLASS_SINGLE_PROBE
  lighting.reflectedColor = EvaluateMainPartSingleReflection(material);
#elif defined(MAIN_PART_TINTED_GLASS_OFF_AMBIENT)
  lighting.reflectedColor = material.gloss * 0.119999997;
#else
  lighting.reflectedColor = 0.0;
#endif
  MainPartGlassSurfaceComposite composite =
      ComposeMainPartTintedTransmissionGlassSurface(
          screenUv, fogColor, frontFace != 0, material, lighting);
  colorTarget = composite.color;
  auxiliaryTarget = composite.auxiliary;
}
