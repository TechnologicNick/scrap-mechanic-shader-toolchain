// Shared opaque G-buffer material evaluation.

struct MainPartGBuffer
{
  float4 albedo;
  float2 encodedNormal;
  float4 material;
  float opacityMask;
};

float2 EncodeMainPartOctahedralNormal(float3 normalView);

// The material frontend is intentionally split from normal evaluation and
// output encoding.  G-buffer permutations can compose only the phases their
// feature set enables without exposing decompiler register temporaries.
float4 SampleMainPartGBufferDiffuse(float2 uv)
{
  return tDif.SampleBias(LinearWrapWrap_s, uv, cb_fMipBias);
}

#if defined(MAIN_PART_GBUFFER_ALPHA_CUTOFF_PHASE)
void ApplyMainPartGBufferAlphaCutoff(float alpha)
{
  if (alpha < 0.5)
    discard;
}
#endif

#if defined(MAIN_PART_GBUFFER_DISSOLVE_PHASE)
#include "main_part_dissolve_cutout.hlsl"

void ApplyMainPartGBufferDissolve(
    float fade, inout MainPartGBuffer result)
{
  float4 dissolveColor = cb_dissolve.vStartColor
      + fade * (cb_dissolve.vEndColor - cb_dissolve.vStartColor);
  result.albedo = dissolveColor
      + fade * (result.albedo - dissolveColor);
}
#endif

#if defined(MAIN_PART_GBUFFER_DIRECTIONAL_MAP_DIFFUSE_PHASE)
void ApplyMainPartGBufferDirectionalMapDiffuse(
    float3 viewPosition,
    float3 normalView,
    float4 vertexColor,
    inout MainPartGBuffer result)
{
  float3 viewDirection = -viewPosition
      * rsqrt(dot(-viewPosition, -viewPosition));
  float3 unitNormal = normalView * rsqrt(dot(normalView, normalView));
  float2 directionalUv = float2(
      dot(unitNormal, cb_vDirectionalLightDirectionView) * -0.5 + 0.5,
      dot(unitNormal, viewDirection));
  directionalUv = min(0.99000001, max(0.00999999978, directionalUv));
  float4 directionalDiffuse = tDif.SampleBias(
      LinearWrapWrap_s, directionalUv, cb_fMipBias);
  result.albedo.xyz = (directionalDiffuse.xyz - vertexColor.xyz)
      * directionalDiffuse.w + vertexColor.xyz;
}
#endif

#if defined(MAIN_PART_GBUFFER_LIGHT_CAP_PHASE) \
    || defined(MAIN_PART_GBUFFER_MAT_CAP_DIFFUSE_PHASE) \
    || defined(MAIN_PART_GBUFFER_MASKED_MAT_CAP_PHASE)
float2 EvaluateMainPartGBufferMatCapUv(
    float3 viewPosition, float3 normalView)
{
  float inverseViewLength = rsqrt(dot(-viewPosition, -viewPosition));
  float3 viewDirection = -viewPosition * inverseViewLength;
  float inverseOnePlusZ = rcp(1.0 + viewDirection.z);
  float3 products = viewDirection.xxy * viewDirection.yxy;
  float2 projected = products.xy * inverseOnePlusZ;
  float projectedZ = 1.0 - products.z * inverseOnePlusZ;
  float3 swizzledNormal = normalView.zxy;
  float3 firstBasis = float3(
      -viewDirection.x, 1.0 - projected.y, projected.x);
  float3 secondBasis = float3(
      -viewDirection.y, projected.x, projectedZ);
  float2 lightCapUv = float2(
      dot(firstBasis, swizzledNormal),
      dot(secondBasis, swizzledNormal));
  return lightCapUv * 0.493999988 + 0.5;
}
#endif

#if defined(MAIN_PART_GBUFFER_LIGHT_CAP_PHASE)
void ApplyMainPartGBufferLightCap(
    float3 viewPosition,
    float3 normalView,
    bool masked,
    inout MainPartGBuffer result)
{
  float2 lightCapUv = EvaluateMainPartGBufferMatCapUv(
      viewPosition, normalView);
  float4 lightCap = tLightCap.Sample(LinearClampClamp_s, lightCapUv);
  float blendWeight = lightCap.w;
  blendWeight *= masked ? result.albedo.w : 1.0;
  result.albedo = (lightCap - result.albedo) * blendWeight
      + result.albedo;
}
#endif

#if defined(MAIN_PART_GBUFFER_MAT_CAP_DIFFUSE_PHASE)
void ApplyMainPartGBufferMatCapDiffuse(
    float3 viewPosition,
    float3 normalView,
    float4 vertexColor,
    inout MainPartGBuffer result)
{
  float2 matCapUv = EvaluateMainPartGBufferMatCapUv(
      viewPosition, normalView);
  float4 matCap = tDif.SampleBias(
      LinearWrapWrap_s, matCapUv, cb_fMipBias);
  result.albedo.xyz = (matCap.xyz - vertexColor.xyz) * matCap.w
      + vertexColor.xyz;
}
#endif

MainPartGBuffer EvaluateMainPartGBufferDiffuseSample(
    float4 diffuse,
    float3 normalView,
    float4 vertexColor)
{
  MainPartGBuffer result;
  result.albedo.xyz = (diffuse.xyz - vertexColor.xyz) * diffuse.w
      + vertexColor.xyz;
  result.albedo.w = 0.0;
  result.encodedNormal = EncodeMainPartOctahedralNormal(normalView);
  result.material = float4(0.0, 0.0, 0.0, 0.0);
  result.opacityMask = 0.0;
  return result;
}

MainPartGBuffer EvaluateMainPartGBufferDiffuse(
    float2 uv,
    float3 normalView,
    float4 vertexColor)
{
  return EvaluateMainPartGBufferDiffuseSample(
      SampleMainPartGBufferDiffuse(uv), normalView, vertexColor);
}

#if defined(MAIN_PART_GBUFFER_AO_PHASE)
void ApplyMainPartGBufferAo(float2 uv, inout MainPartGBuffer result)
{
  float ao = tAo.SampleBias(LinearWrapWrap_s, uv, cb_fMipBias).x;
  result.albedo.xyz *= ao;
}
#endif

#if defined(MAIN_PART_GBUFFER_FACE_ORIENTATION_PHASE)
float3 OrientMainPartGBufferNormal(float3 normalView, bool frontFace)
{
  return frontFace ? normalView : -normalView;
}
#endif

#if defined(MAIN_PART_GBUFFER_ASG_PHASE)
float4 SampleMainPartGBufferAsg(float2 uv)
{
  return tAsg.SampleBias(LinearWrapWrap_s, uv, cb_fMipBias);
}

void ApplyMainPartGBufferAsgSample(
    float4 asgSample,
    float vertexOpacity,
    inout MainPartGBuffer result)
{
  float3 asg = asgSample.yzw;
  result.albedo.w = vertexOpacity * asg.y;
  result.material = float4(asg.z, asg.x, 0.0, 0.0);
  result.opacityMask = asg.y;
}

void ApplyMainPartGBufferAsg(
    float2 uv,
    float vertexOpacity,
    inout MainPartGBuffer result)
{
  ApplyMainPartGBufferAsgSample(
      SampleMainPartGBufferAsg(uv), vertexOpacity, result);
}
#endif

#if defined(MAIN_PART_GBUFFER_MASKED_MAT_CAP_PHASE)
void ApplyMainPartGBufferMaskedMatCap(
    float3 viewPosition,
    float3 normalView,
    bool preserveGlow,
    inout MainPartGBuffer result)
{
  float2 matCapUv = EvaluateMainPartGBufferMatCapUv(
      viewPosition, normalView);
  float3 matCap = tMatCap.Sample(LinearClampClamp_s, matCapUv).xyz;
  result.albedo.xyz = (matCap - result.albedo.xyz) * result.opacityMask
      + result.albedo.xyz;
  result.albedo.w = preserveGlow ? result.albedo.w : 0.0;
}
#endif

#if defined(MAIN_PART_GBUFFER_VERTEX_OCCLUSION_PHASE)
void ApplyMainPartGBufferVertexOcclusion(
    float occlusion, inout MainPartGBuffer result)
{
  result.albedo.xyz *= occlusion;
}
#endif

#if defined(MAIN_PART_GBUFFER_GLOBAL_PULSE_PHASE)
void ApplyMainPartGBufferGlobalPulse(inout MainPartGBuffer result)
{
  result.albedo.w *= cb_fGlobalPulse;
}
#endif

#if defined(MAIN_PART_GBUFFER_NORMAL_PHASE)
float3 EvaluateMainPartGBufferNormalMap(
    float2 uv,
    float3 normalView,
    float3 tangentView,
    float3 bitangentView)
{
  float2 encodedTangentNormal = tNor.SampleBias(
      LinearWrapWrap_s, uv, cb_fMipBias).xy;
  encodedTangentNormal = encodedTangentNormal * 1.99215686 - 1.0;
  float normalZ = dot(encodedTangentNormal, encodedTangentNormal);
  normalZ = sqrt(max(0.0, 1.0 - normalZ));
  float3 decodedNormal = tangentView * encodedTangentNormal.x;
  decodedNormal += bitangentView * encodedTangentNormal.y;
  decodedNormal += normalView * normalZ;
  return decodedNormal;
}
#endif

void WriteMainPartGBuffer(
    MainPartGBuffer value,
    out float4 albedoTarget,
    out float2 normalTarget,
    out float4 materialTarget)
{
  albedoTarget = value.albedo;
  normalTarget = value.encodedNormal;
  materialTarget = value.material;
}

float2 EncodeMainPartOctahedralNormal(float3 normalView)
{
  // Retain the source component order so the compiler follows the recovered
  // normalize and fold sequence used by the G-buffer permutations.
  float3 swizzledNormal = normalView.zxy;
  swizzledNormal *= rsqrt(dot(swizzledNormal, swizzledNormal));
  float l1Norm = abs(swizzledNormal.y) + abs(swizzledNormal.z);
  l1Norm += abs(swizzledNormal.x);
  swizzledNormal /= l1Norm;

  float2 folded = 1.0 - abs(swizzledNormal.zy);
  float3 nonNegative = swizzledNormal >= 0.0;
  float2 foldSign = nonNegative.yz ? 1.0 : -1.0;
  folded *= foldSign;
  float2 octahedral = nonNegative.x ? swizzledNormal.yz : folded;
  return octahedral * 0.5 + 0.5;
}

#if !defined(MAIN_PART_GBUFFER_PHASED)
MainPartGBuffer EvaluateMainPartGBuffer(
    float2 uv,
    float3 normalView,
    float3 tangentView,
    float3 bitangentView,
    float4 vertexColor)
{
  MainPartGBuffer result;

  float4 diffuse = tDif.SampleBias(LinearWrapWrap_s, uv, cb_fMipBias);
  result.albedo.xyz = (diffuse.xyz - vertexColor.xyz) * diffuse.w
      + vertexColor.xyz;

  float3 asg = tAsg.SampleBias(LinearWrapWrap_s, uv, cb_fMipBias).yzw;
  result.albedo.w = vertexColor.w * asg.y;
  result.material = float4(asg.z, asg.x, 0.0, 0.0);
  result.opacityMask = asg.y;

  float2 encodedTangentNormal = tNor.SampleBias(
      LinearWrapWrap_s, uv, cb_fMipBias).xy;
  encodedTangentNormal = encodedTangentNormal * 1.99215686 - 1.0;
  float normalZ = dot(encodedTangentNormal, encodedTangentNormal);
  normalZ = sqrt(max(0.0, 1.0 - normalZ));
  float3 decodedNormal = tangentView * encodedTangentNormal.x;
  decodedNormal += bitangentView * encodedTangentNormal.y;
  decodedNormal += normalView * normalZ;

  result.encodedNormal = EncodeMainPartOctahedralNormal(decodedNormal);
  return result;
}
#endif
