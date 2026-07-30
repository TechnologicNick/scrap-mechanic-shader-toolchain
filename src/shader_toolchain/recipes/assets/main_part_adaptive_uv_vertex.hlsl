#ifndef MAIN_PART_ADAPTIVE_UV_VERTEX_HLSL
#define MAIN_PART_ADAPTIVE_UV_VERTEX_HLSL

float2 EvaluateMainPartAdaptiveScrolledUv(
    float2 baseUv,
    float4 localToWorldRow0,
    float4 localToWorldRow1,
    float4 localToWorldRow2)
{
  const float3 diagonal = float3(
      0.577350269, 0.577350269, 0.577350269);
  float3 transformed = float3(
      dot(localToWorldRow0.xyz, diagonal),
      dot(localToWorldRow1.xyz, diagonal),
      dot(localToWorldRow2.xyz, diagonal));
  float adaptiveScale = 4.0 * sqrt(dot(transformed, transformed));
  return baseUv * adaptiveScale + frac(cb_uvScroll.vSpeed * cb_fTime);
}

#endif // MAIN_PART_ADAPTIVE_UV_VERTEX_HLSL
