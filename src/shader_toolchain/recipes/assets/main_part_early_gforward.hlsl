#ifndef MAIN_PART_EARLY_GFORWARD_HLSL
#define MAIN_PART_EARLY_GFORWARD_HLSL

#include "main_part_octahedral_normal.hlsl"

struct MainPartEarlyGForward
{
  float4 material;
  float2 encodedNormal;
};

#if defined(MAIN_PART_EARLY_GFORWARD_REFLECTION_AS_DIFFUSE_PHASE)
MainPartEarlyGForward EvaluateMainPartReflectionAsDiffuseEarlyGForward(
    float3 normalView)
{
  MainPartEarlyGForward result;
  result.material = float4(0.0, 0.0, 0.0, 0.972549021);
  result.encodedNormal = EncodeMainPartSurfaceNormal(normalView);
  return result;
}
#endif

#if defined(MAIN_PART_EARLY_GFORWARD_OPAQUE_GLASS_PHASE)
MainPartEarlyGForward EvaluateMainPartOpaqueGlassEarlyGForward(
    float2 uv, float3 normalView, float3 tangentView,
    float3 bitangentView, bool frontFace)
{
  MainPartEarlyGForward result;
  float2 asg = tAsg.SampleBias(
      LinearWrapWrap_s, uv, cb_fMipBias).yw;
  result.material = float4(1.0 + asg.y, 1.0 + asg.x,
      0.0, 0.972549021);
  float2 tangentNormal = tNor.SampleBias(
      LinearWrapWrap_s, uv, cb_fMipBias).xy * 1.99215686 - 1.0;
  float normalZ = sqrt(max(0.0, 1.0 - dot(tangentNormal, tangentNormal)));
  float3 mappedNormal = tangentView * tangentNormal.x
      + bitangentView * tangentNormal.y + normalView * normalZ;
  mappedNormal *= rsqrt(dot(mappedNormal, mappedNormal));
  mappedNormal = frontFace ? mappedNormal : -mappedNormal;
  mappedNormal *= rsqrt(dot(mappedNormal, mappedNormal));
  result.encodedNormal = EncodeMainPartSurfaceNormal(mappedNormal);
  return result;
}
#endif

void WriteMainPartEarlyGForward(
    MainPartEarlyGForward value,
    out float4 materialTarget,
    out float2 normalTarget)
{
  materialTarget = value.material;
  normalTarget = value.encodedNormal;
}

#endif
