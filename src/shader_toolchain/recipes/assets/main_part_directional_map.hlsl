#ifndef MAIN_PART_DIRECTIONAL_MAP_INCLUDED
#define MAIN_PART_DIRECTIONAL_MAP_INCLUDED

float2 ResolveMainPartDirectionalMapUv(
    float3 viewPosition, float3 normalView)
{
  float3 viewDirection = -viewPosition
      * rsqrt(dot(-viewPosition, -viewPosition));
  float3 unitNormal = normalView * rsqrt(dot(normalView, normalView));
  float2 directionalUv = float2(
      dot(unitNormal, cb_vDirectionalLightDirectionView.xyz) * -0.5 + 0.5,
      dot(unitNormal, viewDirection));
  return min(0.99000001, max(0.00999999978, directionalUv));
}

float3 SampleMainPartDirectionalMapDiffuse(
    float3 viewPosition, float3 normalView, float4 vertexColor)
{
  float2 directionalUv = ResolveMainPartDirectionalMapUv(
      viewPosition, normalView);
  float4 directionalDiffuse = tDif.SampleBias(
      LinearWrapWrap_s, directionalUv, cb_fMipBias);
  return (directionalDiffuse.xyz - vertexColor.xyz)
      * directionalDiffuse.w + vertexColor.xyz;
}

#endif
