#ifndef MAIN_PART_VERTEX_FOG_HLSL
#define MAIN_PART_VERTEX_FOG_HLSL

// Shared vertex-fog composition used by transparent part surfaces.
//
// The vertex shader precomputes both the fog colour and its combined opacity.
// Pixel permutations can then apply the result without reconstructing world
// height or view distance.

float4 EvaluateMainPartVertexFog(float viewDistance, float worldHeight)
{
  // This family selects the primary atmosphere.  Keeping the index explicit
  // makes the helper extensible to water/secondary-atmosphere permutations.
  const uint fogIndex = 0u;

  float verticalCoordinate = saturate(
      cb_fogs[fogIndex].cb_fVerticalFogInvRange
      * (worldHeight - cb_fogs[fogIndex].cb_fVerticalFogStart));
  float verticalAmount = 1.0 - exp2(
      log2(1.0 - verticalCoordinate)
      * max(cb_fogs[fogIndex].cb_fVerticalFogFalloff, 0.00999999978));
  float4 verticalColor = lerp(
      cb_fogs[fogIndex].cb_vVerticalFogStartColor,
      cb_fogs[fogIndex].cb_vVerticalFogEndColor,
      verticalAmount);
  float verticalFade = 1.0 - saturate(
      cb_fogs[fogIndex].cb_fVerticalFogInvFade * viewDistance);
  verticalFade = (1.0 - verticalFade * verticalFade) * verticalColor.w;

  float distanceCoordinate = saturate(
      cb_fogs[fogIndex].cb_fFogInvRange
      * (viewDistance - cb_fogs[fogIndex].cb_fFogStart));
  float distanceAmount = 1.0 - exp2(
      log2(1.0 - distanceCoordinate)
      * max(cb_fogs[fogIndex].cb_fFogFalloff, 9.99999975e-05));
  float4 distanceColor = lerp(
      cb_fogs[fogIndex].cb_vFogStartColor,
      cb_fogs[fogIndex].cb_vFogEndColor,
      distanceAmount);
  float distanceFade = saturate(
      cb_fogs[fogIndex].cb_fFogInvFade * viewDistance);

  float4 result;
  result.xyz = lerp(distanceColor.xyz, verticalColor.xyz, verticalFade);
  result.w = lerp(
      verticalFade,
      distanceColor.w * distanceFade,
      distanceAmount);
  return result;
}

#endif // MAIN_PART_VERTEX_FOG_HLSL
